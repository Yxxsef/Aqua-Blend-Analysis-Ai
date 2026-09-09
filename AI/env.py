"""Supabase credentials for the AquaBlend project.

Values are read from AI/.env, which is gitignored so keys never reach the
repository. Copy AI/.env.example to AI/.env and fill it in before running
the pipeline.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


# Load AI/.env explicitly: the default search starts at the current working
# directory, so running from the repository root would otherwise miss it.
load_dotenv(Path(__file__).resolve().parent / ".env")


def _required(name: str) -> str:
    """Read one required credential, or explain how to provide it."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy AI/.env.example to AI/.env and fill it in."
        )
    return value


DB_URL = os.environ.get("DB_URL", "")
DB_KEY = os.environ.get("DB_KEY", "")


def require_db_credentials() -> tuple[str, str]:
    """Validate DB_URL/DB_KEY, raising only when a Supabase call is imminent.

    Local JSON mode never calls this, so it must work without either
    variable set. Callers that do need Supabase (a read with no local file,
    or ``--push``) call this right before constructing a client.
    """
    return _required("DB_URL"), _required("DB_KEY")
