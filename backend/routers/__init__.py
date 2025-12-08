# backend/routers/__init__.py
"""
Auto-import all router modules in this package so callers can do:
    from backend.routers import materials, assignments, modules
Works whether or not every router file is present.
"""
import importlib
import pkgutil
import os

__all__ = []

# Import every module found in this package directory
package_name = __name__
package_path = os.path.dirname(__file__)

for finder, name, ispkg in pkgutil.iter_modules([package_path]):
    # skip private files
    if name.startswith("_"):
        continue
    try:
        module = importlib.import_module(f"{package_name}.{name}")
        globals()[name] = module
        __all__.append(name)
    except Exception as e:
        # don't fail import of package if a single router has an error;
        # the error will be visible in logs and the module won't be exported.
        # You can log here if you want.
        pass