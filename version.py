"""Single source of truth for the Mycelium application version.

Mirrors the firmware convention (main/include/version.h): one declaration,
all consumers import from here. Bump this value to change the app version --
run.py and setup.py read it instead of hardcoding their own copies.
"""

__version__ = "2.0.0"
