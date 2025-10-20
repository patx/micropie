# Configuration file for the Sphinx documentation builder.

project = "MicroPie"
author = "Harrison Erd"
release = "0.20"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
]

autosummary_generate = True
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
todo_include_todos = True

intersphinx_mapping = {
<<<<<<< ours
    "python": ("https://docs.python.org/3", {}),
    "asgiref": ("https://asgiref.readthedocs.io/en/latest", {}),
=======
    "python": ("https://docs.python.org/3", None),
    "asgiref": ("https://asgiref.readthedocs.io/en/latest", None),
>>>>>>> theirs
}

templates_path = ["_templates"]
exclude_patterns = []

# Theme settings
html_theme = "alabaster"
html_theme_options = {
    "description": "A minimal ASGI web framework",
    "github_user": "patx",
    "github_repo": "micropie",
    "fixed_sidebar": True,
    "extra_nav_links": {
        "Project README": "https://github.com/patx/micropie",
    },
}

pygments_style = "friendly"
html_static_path = ["_static"]

