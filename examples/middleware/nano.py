"""
nano-asgi: a production-ready ASGI server (pure stdlib).
Run:
  python3 nano.py module:app
  python3 nano.py module:app --certfile cert.pem --keyfile key.pem  # TLS
Key features:
- HTTP/1.1 keep-alive with idle timeout & max-requests-per-conn
- Robust parsing: request-line/header limits, Host required, sane 4xx
- Streaming responses with Transfer-Encoding: chunked (when no Content-Length)
- Expect: 100-continue (only when body is expected)
- HEAD handled (no bytes flushed)
- Access logging (combined format)
- Graceful shutdown & draining; max concurrent connections
- WebSockets (RFC 6455): handshake v13, ping/pong, fragmentation, close
- Configurable: read/write timeouts, backlog, limits
"""

import argparse
import asyncio
import base64
import hashlib
import http
import importlib
import os
import signal
import socket
import ssl as _ssl
import sys
import time
import traceback
from email.utils import formatdate
from typing import Any, Dict, List, Optional, Tuple

SERVER_NAME = b"nano-asgi/1.0"
ASGI_SPEC_VERSION = "2.3"
ASGI_VERSION = "3.0"

# Defaults
DEFAULT_MAX_HEADER_SIZE = 8 * 1024
DEFAULT_MAX_HEADER_COUNT = 100
DEFAULT_MAX_BODY_SIZE = 1 * 1024 * 1024
DEFAULT_READ_TIMEOUT = 30.0
DEFAULT_WRITE_TIMEOUT = 30.0
DEFAULT_REQUEST_LINE_LIMIT = 8 * 1024
DEFAULT_BACKLOG = 512
DEFAULT_KEEPALIVE_TIMEOUT = 15.0
DEFAULT_MAX_REQUESTS_PER_CONN = 100
DEFAULT_MAX_CONNS = 2048


class _CloseConnection(Exception):
    """Internal control flow to close the current connection."""
    pass


class ASGIServer:
    def __init__(
        self,
        app: Any,
        host: str = "0.0.0.0",
        port: int = 8000,
        ssl_context: Optional[_ssl.SSLContext] = None,
        max_header_size: int = DEFAULT_MAX_HEADER_SIZE,
        max_header_count: int = DEFAULT_MAX_HEADER_COUNT,
        max_body_size: int = DEFAULT_MAX_BODY_SIZE,
        read_timeout: float = DEFAULT_READ_TIMEOUT,
        write_timeout: float = DEFAULT_WRITE_TIMEOUT,
        request_line_limit: int = DEFAULT_REQUEST_LINE_LIMIT,
        backlog: int = DEFAULT_BACKLOG,
        keepalive_timeout: float = DEFAULT_KEEPALIVE_TIMEOUT,
        max_requests_per_conn: int = DEFAULT_MAX_REQUESTS_PER_CONN,
        max_conns: int = DEFAULT_MAX_CONNS,
        log_access: bool = True,
        log_debug: bool = False,
        reuse_port: bool = True,
    ) -> None:
        self.app = app
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.max_header_size = max_header_size
        self.max_header_count = max_header_count
        self.max_body_size = max_body_size
        self.read_timeout = read_timeout
        self.write_timeout = write_timeout
        self.request_line_limit = request_line_limit
        self.backlog = backlog
        self.keepalive_timeout = keepalive_timeout
        self.max_requests_per_conn = max_requests_per_conn
        self.reuse_port = reuse_port
        self.shutdown_event = asyncio.Event()
        self._access = log_access
        self._debug = log_debug
        self._conn_sem = asyncio.Semaphore(max_conns)

    # ---------- logging ----------
    def _dbg(self, *args: Any) -> None:
        if self._debug:
            print(*args, file=sys.stderr)

    def _log_access(
        self,
        client: Tuple[str, int],
        method: str,
        target: str,
        version: str,
        status: int,
        resp_bytes: int,
        headers_dict: Dict[str, str],
    ) -> None:
        if not self._access:
            return
        # Common/combined log format
        host = str(client[0]) if isinstance(client, (tuple, list)) else str(client)
        user_ident = "-"
        user_auth = "-"
        ts = time.strftime("%d/%b/%Y:%H:%M:%S %z", time.localtime())
        request_line = f"{method} {target} {version}"
        referer = headers_dict.get("referer", "-")
        ua = headers_dict.get("user-agent", "-")
        line = f'{host} {user_ident} {user_auth} [{ts}] "{request_line}" {status} {resp_bytes} "{referer}" "{ua}"'
        print(line, file=sys.stderr)

    @staticmethod
    def _http_date() -> bytes:
        return formatdate(timeval=None, localtime=False, usegmt=True).encode("ascii")

    async def _drain(self, writer: asyncio.StreamWriter) -> None:
        try:
            await asyncio.wait_for(writer.drain(), timeout=self.write_timeout)
        except asyncio.TimeoutError:
            raise _CloseConnection

    async def _write_error(self, writer: asyncio.StreamWriter, status: int, message: str = "") -> None:
        phrase = http.HTTPStatus(status).phrase
        body = (f"{status} {phrase}\n{message}\n").encode("utf-8", "ignore")
        writer.write(f"HTTP/1.1 {status} {phrase}\r\n".encode("ascii"))
        writer.write(b"Connection: close\r\n")
        writer.write(b"Content-Type: text/plain; charset=utf-8\r\n")
        writer.write(b"Content-Length: " + str(len(body)).encode() + b"\r\n")
        writer.write(b"Date: " + self._http_date() + b"\r\n")
        writer.write(b"Server: " + SERVER_NAME + b"\r\n\r\n")
        writer.write(body)
        await self._drain(writer)

    # ---------- lifecycle ----------
    async def serve(self) -> None:
        # optional lifespan
        lifespan_task = None
        rx: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
        tx: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()

        async def lifespan_receive() -> Dict[str, Any]:
            return await rx.get()

        async def lifespan_send(event: Dict[str, Any]) -> None:
            await tx.put(event)

        if self.app is not None:
            try:
                scope = {"type": "lifespan", "asgi": {"version": ASGI_VERSION, "spec_version": ASGI_SPEC_VERSION}}
                lifespan_task = asyncio.create_task(self.app(scope, lifespan_receive, lifespan_send))
                await rx.put({"type": "lifespan.startup"})
                resp = await asyncio.wait_for(tx.get(), timeout=10.0)
                if resp["type"] == "lifespan.startup.failed":
                    print(f"Startup failed: {resp.get('message', 'Unknown')}", file=sys.stderr)
                    sys.exit(1)
            except Exception:
                # app doesn't implement lifespan — okay
                if lifespan_task:
                    lifespan_task.cancel()
                    await asyncio.gather(lifespan_task, return_exceptions=True)
                lifespan_task = None

        # server socket
        srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT") and self.reuse_port:
            try:
                srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except Exception:
                pass
        try:
            srv_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        srv_sock.bind((self.host, self.port))
        srv_sock.listen(self.backlog)
        srv_sock.setblocking(False)

        server = await asyncio.start_server(
            self._handle_connection_entry,
            sock=srv_sock,
            ssl=self.ssl_context,
            limit=64 * 1024,
        )

        addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
        scheme = "https" if self.ssl_context else "http"
        print(f"nano-asgi listening on {scheme}://{addrs}", file=sys.stderr)

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.shutdown_event.set)
            except NotImplementedError:
                pass

        async with server:
            serve_task = asyncio.create_task(server.serve_forever())
            await self.shutdown_event.wait()
            # stop accepting
            server.close()
            await server.wait_closed()
            # let current connections drain a bit
            await asyncio.sleep(0.25)
            await asyncio.gather(serve_task, return_exceptions=True)

        if lifespan_task:
            try:
                await rx.put({"type": "lifespan.shutdown"})
                _ = await asyncio.wait_for(tx.get(), timeout=10.0)
            except Exception:
                pass
            finally:
                lifespan_task.cancel()
                await asyncio.gather(lifespan_task, return_exceptions=True)

        print("nano-asgi shutdown complete", file=sys.stderr)

    async def _handle_connection_entry(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        async with self._conn_sem:
            await self.handle_connection(reader, writer)

    # ---------- connection ----------
    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        client = writer.get_extra_info("peername") or ("unknown", 0)
        server = writer.get_extra_info("sockname")
        scheme = "https" if self.ssl_context else "http"
        self._dbg(f"Connection from {client}")
        requests_handled = 0
        last_activity = time.monotonic()

        try:
            while True:
                if self.shutdown_event.is_set():
                    # refuse new requests on this connection
                    break
                if time.monotonic() - last_activity > self.keepalive_timeout:
                    break
                if requests_handled >= self.max_requests_per_conn:
                    break

                # --- Request line ---
                try:
                    line = await asyncio.wait_for(reader.readline(), self.read_timeout)
                except asyncio.TimeoutError:
                    break
                if not line:
                    break
                if len(line) > self.request_line_limit:
                    await self._write_error(writer, 414, "Request-URI Too Long")
                    break

                try:
                    req_line = line.decode("ascii", errors="strict").rstrip("\r\n")
                except UnicodeDecodeError:
                    await self._write_error(writer, 400, "Invalid request line encoding")
                    break

                parts = req_line.split()
                if len(parts) != 3:
                    await self._write_error(writer, 400, "Malformed request line")
                    break
                method, target, version = parts
                method = method.upper()
                if version.upper() != "HTTP/1.1":
                    await self._write_error(writer, 505, "HTTP Version Not Supported")
                    break

                # Absolute-form support (proxies) — extract path & host
                path, query_bytes, raw_path = self._split_target(target)

                # --- Headers (preserve dups) ---
                headers_list: List[Tuple[bytes, bytes]] = []
                headers_first: Dict[str, str] = {}
                total_bytes = 0
                header_count = 0
                while True:
                    try:
                        line_b = await asyncio.wait_for(reader.readline(), self.read_timeout)
                    except asyncio.TimeoutError:
                        await self._write_error(writer, 408, "Request Timeout")
                        return
                    if not line_b:
                        return  # client hung up
                    total_bytes += len(line_b)
                    if total_bytes > self.max_header_size:
                        await self._write_error(writer, 431, "Request Header Fields Too Large")
                        return
                    if line_b == b"\r\n":
                        break
                    try:
                        k, v = line_b.decode("latin-1").rstrip("\r\n").split(":", 1)
                    except ValueError:
                        # skip malformed header
                        continue
                    header_count += 1
                    if header_count > self.max_header_count:
                        await self._write_error(writer, 431, "Too many headers")
                        return
                    k_l = k.strip().lower()
                    v_s = v.strip()
                    headers_list.append((k_l.encode("latin-1"), v_s.encode("latin-1")))
                    if k_l not in headers_first:
                        headers_first[k_l] = v_s

                # Host header required in HTTP/1.1
                if "host" not in headers_first:
                    await self._write_error(writer, 400, "Host header required")
                    break

                # Connection semantics
                conn_tokens = {t.strip().lower() for t in headers_first.get("connection", "").split(",") if t.strip()}
                client_wants_close = "close" in conn_tokens

                # Expect: 100-continue
                expect_100 = headers_first.get("expect", "").lower() == "100-continue"

                # Upgrade: websocket?
                is_ws = ("upgrade" in conn_tokens) and headers_first.get("upgrade", "").lower() == "websocket"

                # Build scope
                if is_ws:
                    scope: Dict[str, Any] = {
                        "type": "websocket",
                        "asgi": {"version": ASGI_VERSION, "spec_version": ASGI_SPEC_VERSION},
                        "scheme": scheme,
                        "server": server,
                        "client": client,
                        "path": path,
                        "raw_path": raw_path,
                        "query_string": query_bytes,
                        "headers": headers_list,
                        "subprotocols": [s.strip() for s in headers_first.get("sec-websocket-protocol", "").split(",") if s.strip()],
                    }
                else:
                    scope = {
                        "type": "http",
                        "asgi": {"version": ASGI_VERSION},
                        "http_version": "1.1",
                        "method": method,
                        "scheme": scheme,
                        "path": path,
                        "raw_path": raw_path,
                        "query_string": query_bytes,
                        "headers": headers_list,
                        "client": client,
                        "server": server,
                    }

                self._dbg(f"Scope for {client}: {scope}")

                # Prepare receive queue and body task
                # Send 100-Continue right before reading a body (only if body is expected)
                will_have_body = self._request_has_body(method, headers_first)
                if expect_100 and will_have_body:
                    writer.write(b"HTTP/1.1 100 Continue\r\n\r\n")
                    await self._drain(writer)

                receive_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
                body_task = asyncio.create_task(
                    self._body_reader(reader, writer, receive_queue, headers_first, is_ws)
                )

                # Response state
                sent_start = False
                response_status = 200
                response_bytes = 0
                close_after_response = client_wants_close or self.shutdown_event.is_set()
                is_head = (method == "HEAD")
                write_chunked = False
                # We decide chunked at response.start time if no Content-Length set by app
                pending_headers: List[Tuple[bytes, bytes]] = []

                async def receive() -> Dict[str, Any]:
                    return await receive_queue.get()

                async def send(event: Dict[str, Any]) -> None:
                    nonlocal sent_start, write_chunked, response_status, response_bytes, close_after_response, pending_headers
                    etype = event["type"]
                    self._dbg(f"Send event for {client}: {event}")

                    if etype == "http.response.start":
                        if sent_start:
                            return
                        sent_start = True
                        response_status = int(event["status"])
                        out_headers: List[Tuple[bytes, bytes]] = list(event.get("headers", []))

                        # Normalize header keys to bytes and check presence
                        lower_keys = {hk.lower(): hv for hk, hv in out_headers}
                        has_len = any(hk.lower() == b"content-length" for hk, _ in out_headers)
                        has_conn = any(hk.lower() == b"connection" for hk, _ in out_headers)
                        has_te = any(hk.lower() == b"transfer-encoding" for hk, _ in out_headers)

                        # Decide TE: chunked if we don't have Content-Length
                        if not has_len and not has_te:
                            write_chunked = True
                            out_headers.append((b"Transfer-Encoding", b"chunked"))

                        # Add server/date and connection
                        out_headers.append((b"Date", self._http_date()))
                        out_headers.append((b"Server", SERVER_NAME))
                        if not has_conn:
                            out_headers.append((b"Connection", b"close" if close_after_response else b"keep-alive"))

                        # Write start line & headers
                        writer.write(f"HTTP/1.1 {response_status} {http.HTTPStatus(response_status).phrase}\r\n".encode("ascii"))
                        for k, v in out_headers:
                            writer.write(k + b": " + v + b"\r\n")
                        writer.write(b"\r\n")
                        pending_headers = out_headers  # for debugging/inspection
                        await self._drain(writer)

                    elif etype == "http.response.body":
                        if not sent_start:
                            await send({"type": "http.response.start", "status": response_status, "headers": []})

                        body = event.get("body", b"") or b""
                        more = bool(event.get("more_body", False))

                        if not is_head:
                            if write_chunked:
                                if body:
                                    writer.write(hex(len(body))[2:].encode("ascii") + b"\r\n")
                                    writer.write(body + b"\r\n")
                                    response_bytes += len(body)
                                if not more:
                                    writer.write(b"0\r\n\r\n")
                            else:
                                if body:
                                    writer.write(body)
                                    response_bytes += len(body)
                        # on HEAD: suppress writes but still respect 'more_body'
                        await self._drain(writer)

                        if not more:
                            if close_after_response:
                                raise _CloseConnection

                    elif etype == "http.response.trailers":
                        # We do not advertise TE: trailers; ignore.
                        pass

                    elif etype == "websocket.accept":
                        key = headers_first.get("sec-websocket-key")
                        version = headers_first.get("sec-websocket-version", "")
                        if not key or version.strip() != "13":
                            await self._write_error(writer, 400, "Bad WebSocket handshake")
                            raise _CloseConnection
                        accept_hash = base64.b64encode(
                            hashlib.sha1(key.encode("ascii") + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest()
                        )
                        subprotocol = event.get("subprotocol")
                        extra = event.get("headers", [])
                        writer.write(b"HTTP/1.1 101 Switching Protocols\r\n")
                        writer.write(b"Upgrade: websocket\r\n")
                        writer.write(b"Connection: Upgrade\r\n")
                        writer.write(b"Sec-WebSocket-Accept: " + accept_hash + b"\r\n")
                        if subprotocol:
                            writer.write(b"Sec-WebSocket-Protocol: " + subprotocol.encode("ascii") + b"\r\n")
                        for k, v in extra:
                            writer.write(k + b": " + v + b"\r\n")
                        writer.write(b"\r\n")
                        await self._drain(writer)

                    elif etype == "websocket.send":
                        if "text" in event and event["text"] is not None:
                            frame = self._build_ws_frame(0x1, event["text"].encode("utf-8"))
                        elif "bytes" in event and event["bytes"] is not None:
                            frame = self._build_ws_frame(0x2, event["bytes"])
                        else:
                            return
                        writer.write(frame)
                        await self._drain(writer)

                    elif etype == "websocket.close":
                        code = int(event.get("code", 1000))
                        reason = (event.get("reason", "") or "").encode("utf-8")
                        payload = code.to_bytes(2, "big") + reason
                        frame = self._build_ws_frame(0x8, payload)
                        writer.write(frame)
                        await self._drain(writer)
                        raise _CloseConnection

                # Run the app
                try:
                    await self.app(scope, receive, send)
                except _CloseConnection:
                    pass
                except Exception as e:
                    self._dbg(f"Application error for {client}: {e}")
                    traceback.print_exc(file=sys.stderr)
                    if not is_ws:
                        try:
                            await self._write_error(writer, 500, "Internal Server Error")
                        except Exception:
                            pass
                    break
                finally:
                    if not body_task.done():
                        body_task.cancel()
                    await asyncio.gather(body_task, return_exceptions=True)

                # Access log once response finished (best-effort)
                self._log_access(
                    client=client,
                    method=method,
                    target=target,
                    version=version,
                    status=response_status,
                    resp_bytes=response_bytes if not is_head else 0,
                    headers_dict=headers_first,
                )

                requests_handled += 1
                if is_ws:
                    break  # one websocket per TCP conn
                last_activity = time.monotonic()

        except Exception as e:
            self._dbg(f"Connection error for {client}: {e}")
            traceback.print_exc(file=sys.stderr)
        finally:
            if not writer.is_closing():
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
            self._dbg(f"Connection closed for {client}")

    # ---------- helpers ----------
    def _split_target(self, target: str) -> Tuple[str, bytes, bytes]:
        # Supports origin-form and absolute-form targets.
        raw_path = target.encode("ascii", errors="ignore")
        if "://" in target:
            # absolute-form: scheme://host[:port]/path?query
            # We only need path+query
            p = target.split("://", 1)[1]
            if "/" in p:
                p = p[p.find("/") :]
            else:
                p = "/"
            t = p
        else:
            t = target

        if "?" in t:
            path, q = t.split("?", 1)
            q_b = q.encode("ascii", errors="ignore")
        else:
            path, q_b = t, b""
        return path or "/", q_b, raw_path

    def _request_has_body(self, method: str, headers_first: Dict[str, str]) -> bool:
        # Per RFC, GET/HEAD usually no body, but may have. Here we only expect when client declares it.
        if "content-length" in headers_first:
            try:
                return int(headers_first["content-length"]) > 0
            except Exception:
                return False
        if "transfer-encoding" in headers_first and "chunked" in headers_first["transfer-encoding"].lower():
            return True
        return False

    # ---------- body reader / websocket ----------
    async def _body_reader(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        queue: "asyncio.Queue[Dict[str, Any]]",
        headers_first: Dict[str, str],
        is_ws: bool,
    ) -> None:
        try:
            if is_ws:
                await queue.put({"type": "websocket.connect"})
                # WS fragmentation support
                frag_opcode = None
                frag_buf = bytearray()
                while True:
                    opcode, fin, payload, masked = await self._read_ws_frame(reader)
                    if not masked:
                        # client MUST mask
                        await queue.put({"type": "websocket.disconnect", "code": 1002})
                        break
                    if opcode == 0x0:  # continuation
                        if frag_opcode is None:
                            await queue.put({"type": "websocket.disconnect", "code": 1002})
                            break
                        frag_buf.extend(payload)
                        if fin:
                            # deliver whole message
                            if frag_opcode == 0x1:
                                await queue.put({"type": "websocket.receive", "text": frag_buf.decode("utf-8", "ignore")})
                            else:
                                await queue.put({"type": "websocket.receive", "bytes": bytes(frag_buf)})
                            frag_buf.clear()
                            frag_opcode = None
                    elif opcode in (0x1, 0x2):  # text/binary
                        if fin:
                            if opcode == 0x1:
                                await queue.put({"type": "websocket.receive", "text": payload.decode("utf-8", "ignore")})
                            else:
                                await queue.put({"type": "websocket.receive", "bytes": payload})
                        else:
                            frag_opcode = opcode
                            frag_buf.extend(payload)
                    elif opcode == 0x8:  # close
                        code = int.from_bytes(payload[:2], "big") if len(payload) >= 2 else 1000
                        await queue.put({"type": "websocket.disconnect", "code": code})
                        # echo close frame
                        frame = self._build_ws_frame(0x8, payload)
                        writer.write(frame)
                        await self._drain(writer)
                        break
                    elif opcode == 0x9:  # ping -> pong
                        frame = self._build_ws_frame(0xA, payload)
                        writer.write(frame)
                        await self._drain(writer)
                    elif opcode == 0xA:  # pong
                        pass
                    else:
                        await queue.put({"type": "websocket.disconnect", "code": 1002})
                        break
            else:
                cl = headers_first.get("content-length")
                te = headers_first.get("transfer-encoding", "").lower()
                total = 0

                if cl is None and "chunked" not in te:
                    # no body
                    await queue.put({"type": "http.request", "body": b"", "more_body": False})
                    return

                if cl is not None and "chunked" in te:
                    raise ValueError("Both Content-Length and Transfer-Encoding set")

                if cl is not None:
                    try:
                        clen = int(cl)
                        if clen < 0:
                            raise ValueError
                    except Exception:
                        raise ValueError("Invalid Content-Length")
                    if clen == 0:
                        await queue.put({"type": "http.request", "body": b"", "more_body": False})
                        return
                    if clen > self.max_body_size:
                        raise ValueError("Body too large")
                    remaining = clen
                    while remaining:
                        chunk = await asyncio.wait_for(reader.read(min(65536, remaining)), self.read_timeout)
                        if not chunk:
                            await queue.put({"type": "http.disconnect"})
                            return
                        remaining -= len(chunk)
                        total += len(chunk)
                        await queue.put({"type": "http.request", "body": chunk, "more_body": remaining > 0})
                else:
                    # chunked
                    while True:
                        line = await asyncio.wait_for(reader.readline(), self.read_timeout)
                        if not line:
                            await queue.put({"type": "http.disconnect"})
                            return
                        try:
                            size = int(line.strip().split(b";", 1)[0], 16)
                        except Exception:
                            raise ValueError("Invalid chunk size")
                        if size == 0:
                            # read trailers until CRLF
                            while True:
                                t = await asyncio.wait_for(reader.readline(), self.read_timeout)
                                if t in (b"", b"\r\n"):
                                    break
                            await queue.put({"type": "http.request", "body": b"", "more_body": False})
                            break
                        if total + size > self.max_body_size:
                            raise ValueError("Body too large")
                        data = await asyncio.wait_for(reader.readexactly(size), self.read_timeout)
                        total += size
                        await queue.put({"type": "http.request", "body": data, "more_body": True})
                        # trailing CRLF
                        _ = await asyncio.wait_for(reader.readexactly(2), self.read_timeout)

        except asyncio.TimeoutError:
            await queue.put({"type": "http.disconnect" if not is_ws else "websocket.disconnect"})
        except Exception as e:
            print(f"Body reader error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            await queue.put({"type": "http.disconnect" if not is_ws else "websocket.disconnect"})

    def _build_ws_frame(self, opcode: int, payload: bytes) -> bytes:
        # server frames unmasked
        n = len(payload)
        out = bytearray()
        out.append(0x80 | opcode)
        if n < 126:
            out.append(n)
        elif n < (1 << 16):
            out.append(126)
            out.extend(n.to_bytes(2, "big"))
        else:
            out.append(127)
            out.extend(n.to_bytes(8, "big"))
        out.extend(payload)
        return bytes(out)

    async def _read_ws_frame(self, reader: asyncio.StreamReader) -> Tuple[int, bool, bytes, bool]:
        head = await asyncio.wait_for(reader.readexactly(2), self.read_timeout)
        fin = (head[0] & 0x80) != 0
        opcode = head[0] & 0x0F
        masked = (head[1] & 0x80) != 0
        length = head[1] & 0x7F
        if length == 126:
            length = int.from_bytes(await asyncio.wait_for(reader.readexactly(2), self.read_timeout), "big")
        elif length == 127:
            length = int.from_bytes(await asyncio.wait_for(reader.readexactly(8), self.read_timeout), "big")
        mask_key = await asyncio.wait_for(reader.readexactly(4), self.read_timeout) if masked else None
        payload = await asyncio.wait_for(reader.readexactly(length), self.read_timeout)
        if masked and mask_key:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        # validate control frames
        if opcode in (0x8, 0x9, 0xA) and len(payload) > 125:
            raise ValueError("Control frame too large")
        return opcode, fin, payload, masked

    # ---------- app loader ----------
    def load_app(self, app_string: str) -> Any:
        try:
            module_name, app_name = app_string.split(":")
        except ValueError:
            print("Error: Application must be specified as 'module:application'", file=sys.stderr)
            sys.exit(1)
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            print(f"Error: Cannot import module '{module_name}': {e}", file=sys.stderr)
            sys.exit(1)
        try:
            app = getattr(module, app_name)
        except AttributeError:
            print(f"Error: Cannot find application '{app_name}' in module '{module_name}'", file=sys.stderr)
            sys.exit(1)
        return app


def build_ssl_context(certfile: Optional[str], keyfile: Optional[str]) -> Optional[_ssl.SSLContext]:
    if not certfile or not keyfile:
        return None
    ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_SERVER)
    ctx.options |= _ssl.OP_NO_SSLv2 | _ssl.OP_NO_SSLv3
    ctx.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!MD5:!3DES")
    ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)
    # OCSP/ALPN could be added here; we keep it simple.
    return ctx


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run an ASGI application (nano-asgi)")
    parser.add_argument("app", help="ASGI application as module:application")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--certfile")
    parser.add_argument("--keyfile")
    parser.add_argument("--max-header", type=int, default=DEFAULT_MAX_HEADER_SIZE)
    parser.add_argument("--max-header-count", type=int, default=DEFAULT_MAX_HEADER_COUNT)
    parser.add_argument("--max-body", type=int, default=DEFAULT_MAX_BODY_SIZE)
    parser.add_argument("--read-timeout", type=float, default=DEFAULT_READ_TIMEOUT)
    parser.add_argument("--write-timeout", type=float, default=DEFAULT_WRITE_TIMEOUT)
    parser.add_argument("--keepalive-timeout", type=float, default=DEFAULT_KEEPALIVE_TIMEOUT)
    parser.add_argument("--backlog", type=int, default=DEFAULT_BACKLOG)
    parser.add_argument("--max-requests-per-conn", type=int, default=DEFAULT_MAX_REQUESTS_PER_CONN)
    parser.add_argument("--max-conns", type=int, default=DEFAULT_MAX_CONNS)
    parser.add_argument("--no-access-log", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-reuse-port", action="store_true")
    args = parser.parse_args()

    ssl_ctx = build_ssl_context(args.certfile, args.keyfile)

    try:
        server = ASGIServer(
            None,
            host=args.host,
            port=args.port,
            ssl_context=ssl_ctx,
            max_header_size=args.max_header,
            max_header_count=args.max_header_count,
            max_body_size=args.max_body,
            read_timeout=args.read-timeout if hasattr(args, "read-timeout") else args.read_timeout,  # robust to shells
            write_timeout=args.write_timeout,
            backlog=args.backlog,
            keepalive_timeout=args.keepalive_timeout,
            max_requests_per_conn=args.max_requests_per_conn,
            max_conns=args.max_conns,
            log_access=not args.no_access_log,
            log_debug=args.debug,
            reuse_port=not args.no_reuse_port,
        )
        app = server.load_app(args.app)
        server.app = app
    except SystemExit:
        sys.exit(1)

    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        print("Received shutdown signal", file=sys.stderr)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

