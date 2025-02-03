"""

MicroPie is Fun
```````````````

::

    from MicroPie import

    class MyApp(Server):

        def index(self):
            return 'Hello world!'

    app = MyApp()  # Run with `uvicorn app:app`


Links
`````

* `Website <https://patx.github.io/micropie>`_
* `Github Repo <https://github.com/patx/micropie>`_
"""

from distutils.core import setup

setup(name="MicroPie",
    version="0.9.5",
    description="A ultra micro web framework w/ Jinja2.",
    long_description=__doc__,
    author="Harrison Erd",
    author_email="harrisonerd@gmail.com",
    license="three-clause BSD",
    url="http://github.com/patx/micropie",
    classifiers = [
    "Programming Language :: Python :: 3",
    "Environment :: Web Environment",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: BSD License",
    "Operating System :: OS Independent",
    "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    "Topic :: Internet :: WWW/HTTP :: WSGI",
    "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
    "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
    "Framework :: AsyncIO",
    "Topic :: Software Development :: Libraries :: Application Frameworks",
    "Typing :: Typed"],
    py_modules=['MicroPie'],
    install_requires=['jinja2'],
)

