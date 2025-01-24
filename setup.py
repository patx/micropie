"""
MicroPie
--------

MicroPie is lightweight, fast, and simple micro WSGI framework inspired by CherryPy. And it's BSD licensed!


MicroPie is Fun
```````````````

::

    from MicroPie import Server

    class MyApp(Server):

        def index(self):
            return 'Hello world!'

    MyApp().run()


And Easy to Install
```````````````````

::

    $ pip install micropie


Links
`````

* `Website <https://patx.github.io/micropie>`_
* `Github Repo <https://github.com/patx/micropie>`_
"""

from distutils.core import setup

setup(name="MicroPie",
    version="0.5",
    description="A ultra micro web framework w/ Jinja2.",
    long_description=__doc__,
    author="Harrison Erd",
    author_email="harrisonerd@gmail.com",
    license="three-clause BSD",
    url="http://github.com/patx/micropie",
    classifiers = [
        "Programming Language :: Python",
        "License :: OSI Approved :: BSD License",
        "Intended Audience :: Developers"],
    py_modules=['MicroPie'],
    install_requires=['jinja2'],
)

