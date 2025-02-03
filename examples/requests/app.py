from MicroPie import App

# Request handlers defined outside the class

def get_handler():
    return b"Hello, GET request received!"

def post_handler():
    return b"Hello, POST request received!"

def put_handler():
    return b"Hello, PUT request received!"

def patch_handler():
    return b"Hello, PATCH request received!"

def delete_handler():
    return b"Hello, DELETE request received!"

def head_handler():
    # Return status 200 with empty body and proper headers
    return 200, b"", [("Content-Type", "text/html")]

def options_handler():
    # Return the allowed methods in the response header and message in bytes
    return 200, b"Allowed methods: GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD", [
        ("Allow", "GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD")
    ]

# Define the custom server application
class Root(App):

    # Handle root URL requests and delegate based on HTTP method
    def index(self):
        return self.handle_request()

    def handle_request(self):
        # Map request methods to their corresponding handler functions
        method_map = {
            "GET": get_handler,
            "POST": post_handler,
            "PUT": put_handler,
            "PATCH": patch_handler,
            "DELETE": delete_handler,
            "HEAD": head_handler,
            "OPTIONS": options_handler,
        }

        # Check if the request method is supported and call the handler
        if self.request.method in method_map:
            response = method_map[self.scope['method']]()

            # Ensure response is formatted correctly for WSGI
            if isinstance(response, tuple):
                status_code, response_body, headers = response
            else:
                status_code, response_body, headers = 200, response, [("Content-Type", "text/html")]

            return status_code, response_body, headers

        # Return 405 if the request method is not supported
        return 405, b"405 Method Not Allowed", [("Content-Type", "text/html")]



app = Root()
