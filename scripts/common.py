"""Shared helpers for the scripts in this folder (run them from the repository root)."""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

USER_AGENT = "wikes-preprocessing/1.0 (research; https://github.com/msorkhpar/wiki-entity-summarization)"


def http_get(url: str, data: bytes | None = None, headers: dict | None = None) -> urllib.request.addinfourl:
    request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    return urllib.request.urlopen(request, timeout=300)


def pg_connection():
    import psycopg2
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432"), dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"),
    )
