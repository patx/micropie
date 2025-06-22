[![Logo](https://patx.github.io/micropie/logo.png)](https://patx.github.io/micropie)

MicroPie is an ultra-micro ASGI Python web framework that gets out of your way, 
letting you build fast and dynamic web apps with ease. Inspired by CherryPy and
licensed under the BSD three-clause license.

### MicroPie is Fun
```python
from MicroPie import App

class MyApp(App):

    async def index(self):
        return "Hello World!"

app = MyApp()  # Run with `uvicorn app:app`
```

### And Easy to Install
```bash
$ pip install micropie
```
