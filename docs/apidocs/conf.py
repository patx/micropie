# Configuration file for the Sphinx documentation builder.

project = "MicroPie"
author = "Harrison Erd"
release = "0.20"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns = []

# Theme settings
html_theme = "alabaster"
html_theme_options = {
    "description": "A minimal ASGI web framework",
    "github_user": "patx",
    "github_repo": "micropie",
    "fixed_sidebar": True,
}
html_static_path = ["_static"]

