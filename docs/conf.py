"""Sphinx configuration for the hopcheck documentation."""

import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "hopcheck"
author = "Michal Lip"
copyright = "2026, Michal Lip"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = []
exclude_patterns = ["_build"]

html_theme = "alabaster"
html_static_path = []
html_title = "hopcheck"

html_theme_options = {
    "description": "See every hop of a redirect chain, not just where it lands.",
    "github_user": "theluckystrike",
    "github_repo": "hopcheck",
    "github_button": False,
    "fixed_sidebar": True,
}

autodoc_member_order = "bysource"
autodoc_typehints = "description"
