"""Data layer for A."""

from A.data.base import SQLiteDB
from A.data.search import FTSConfig, build_fts_schema, build_search_query

__all__ = ["SQLiteDB", "FTSConfig", "build_fts_schema", "build_search_query"]