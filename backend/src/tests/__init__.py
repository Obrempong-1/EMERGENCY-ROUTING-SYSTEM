"""Test package. Severs every connection to real infrastructure before config loads."""

import os

_PRODUCTION_VARS = (
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
)

for _name in _PRODUCTION_VARS:
    os.environ.pop(_name, None)

os.environ["DATABASE_URL"] = ""
