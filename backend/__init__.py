# backend/__init__.py
# This file makes 'backend' a package.
from .app import app, fs, mail

# By importing app, fs, and mail here, they become accessible
# as attributes of the 'backend' package, e.g., backend.app, backend.fs.
# Blueprints can then use `from .. import fs` or `from ..app import fs`
# depending on how they are structured.
# The circular import issue arose because app.py imports blueprints,
# which then tried to import fs from backend's __init__ before app.py finished defining fs.

# A more robust solution is often the app factory pattern,
# but this change aims to resolve the immediate circular import.
# We are keeping fs and mail exposed here for now, as blueprints
# like customer_actions_bp.py were trying `from .. import fs`.
# The key is that app.py itself does not try to import `backend.fs` or `backend.mail`
# at the top level, but rather defines them, and they are exposed here.
# The problem was likely the timing and order of module initialization.

# Let's re-evaluate:
# conftest -> backend.app (causes backend/__init__ to run)
# backend/__init__ -> .app (app, fs, mail)
# .app -> blueprints -> customer_actions_bp
# customer_actions_bp -> .. (which is backend, trying to get fs from backend/__init__)

# The circularity is: backend/__init__.py imports .app.fs, but .app needs to be fully loaded.
# While .app is loading, it loads blueprints, which load backend/__init__.py (for fs).

# Alternative for __init__.py:
# Only import app here. Blueprints must import fs & mail directly from .app
# from .app import app

# Let's try this minimal approach for __init__.py:
# This makes `app` available as `backend.app`.
# Blueprints will need to change how they import fs and mail.
# from .app import app
# No, the original problem was `cannot import name 'fs' from 'backend'`, so `fs` *needs* to be in `backend/__init__`.
# The issue is that `app.py` imports blueprints *before* `fs` is truly "registered" at the package level.

# Let's stick to the original idea for this file:
# from .app import app, fs, mail
# And ensure that in app.py, blueprint imports are done carefully.
# However, app.py already defines fs and mail BEFORE importing blueprints.

# The "partially initialized module" error means `backend` (i.e. `backend/__init__.py`)
# is trying to import something from itself that isn't fully baked yet due to the recursion.

# What if `app.py` imports `fs` and `mail` from `col.py` or a new `extensions.py`?
# `app.py`:
#   `app = Flask()`
#   `from .extensions import fs, mail, db` (initialize them in extensions.py)
#   `from .blueprints import ...`
#   `app.register_blueprint(...)`

# `extensions.py`:
#   `from flask_pymongo import MongoClient`
#   `import gridfs`
#   `# ... setup db ...`
#   `fs = gridfs.GridFS(db)`
#   `# ... setup mail ...`
#   `mail = Mail()` -> needs app, so this must be `mail.init_app(app)` later.

# This is getting complex. The simplest fix is often to change the import style in the blueprints.
# Instead of `from .. import fs`, use `from ..app import fs`.

# So, for now, `backend/__init__.py` will be left as exposing app, fs, mail.
# The fix will be in the blueprints.
from .app import app, fs, mail
