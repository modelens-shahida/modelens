import os
import sys

# Resolve the path to the backend FastAPI application package
backend_app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'app'))

# Insert the backend app path at the start of sys.path if not already present
if backend_app_path not in sys.path:
    sys.path.insert(0, backend_app_path)

# Extend this package's __path__ so submodules (models, config, middleware, etc.) are found
if backend_app_path not in __path__:
    __path__.append(backend_app_path)

