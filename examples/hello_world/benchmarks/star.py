from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route

async def index(request):
    return HTMLResponse(f"Hello World!")

app = Starlette(routes=[Route("/", index)])
