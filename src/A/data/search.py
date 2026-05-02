"""FTS5 search schema generation and query building.

Usage:
    from A.data.search import FTSConfig, build_fts_schema, build_search_query

    config = FTSConfig(
        table="vorto",
        fts_columns=["teksto"],
        filter_columns=["lingvo", "kategorio", "tipo", "temo"],
    )
    create_sql = build_fts_schema(config)
    query, params = build_search_query(config, query="hello", filters={"lingvo": "fr"})
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from A.utils.normalize import fold_search_text


@dataclass
class FTSConfig:
    """Configuration for FTS5 full-text search on a table.

    Attributes:
        table: Main table name
        fts_table: FTS virtual table name (default: {table}_fts)
        fts_columns: Columns from main table to index in FTS5
        tokenize: FTS5 tokenizer (default: "unicode61")
        filter_columns: Columns for WHERE filters (indexes auto-created)
        normalize: Column → normalization function for FTS content
    """

    table: str
    fts_columns: list[str]
    fts_table: str = ""
    tokenize: str = "unicode61"
    filter_columns: list[str] = field(default_factory=list)
    normalize: dict[str, Callable[[str], str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.fts_table:
            self.fts_table = f"{self.table}_fts"
        # Default: normalize all text columns with fold_search_text
        if not self.normalize:
            self.normalize = {col: fold_search_text for col in self.fts_columns}


def build_fts_schema(config: FTSConfig) -> list[str]:
    """Build SQL statements to create FTS5 virtual table + filter indexes.

    Args:
        config: FTS5 configuration

    Returns:
        List of SQL statements to execute
    """
    columns_def = ", ".join(f"{col}" for col in config.fts_columns)
    statements = [
        f"""CREATE VIRTUAL TABLE IF NOT EXISTS {config.fts_table}
            USING fts5(
                uuid UNINDEXED,
                {columns_def},
                content={config.table},
                content_rowid=rowid,
                tokenize='{config.tokenize}'
            )""",
    ]
    for col in config.filter_columns:
        statements.append(
            f"CREATE INDEX IF NOT EXISTS idx_{config.table}_{col} "
            f"ON {config.table}({col})"
        )
    return statements


def build_search_query(
    config: FTSConfig,
    query: str,
    filters: dict[str, str] | None = None,
    order_by: str = "relevance",
    limit: int = 50,
    offset: int = 0,
) -> tuple[str, list]:
    """Build a search SQL with FTS5 + filters + sort.

    Args:
        config: FTS5 configuration
        query: User search query (auto-normalized)
        filters: Column→value exact match filters
        order_by: "relevance" (default), "date", or column name
        limit: Max results
        offset: Pagination offset

    Returns:
        (sql, params) tuple ready for db.execute()
    """
    # Normalize search query (mirrors how FTS content was normalized)
    if config.normalize:
        # Use any normalizer (they all do the same folding for search)
        norm_fn = next(iter(config.normalize.values()))
        normalized_query = norm_fn(query)
    else:
        normalized_query = query

    # Escape FTS5 special characters and wrap in quotes for phrase matching
    escaped = normalized_query.replace('"', '""')
    fts_query = f'"{escaped}"'

    where_clauses = [f"{config.fts_table} MATCH ?"]
    params: list = [fts_query]

    for field, value in (filters or {}).items():
        if value is not None and value != "":
            where_clauses.append(f"{config.table}.{field} = ?")
            params.append(value)

    if order_by == "relevance":
        order_clause = "rank"
    elif order_by == "date":
        order_clause = f"{config.table}.kreita_je DESC"
    elif order_by == "date_asc":
        order_clause = f"{config.table}.kreita_je ASC"
    else:
        order_clause = f"{config.table}.{order_by}"

    sql = f"""
    SELECT {config.table}.* FROM {config.table}
    JOIN {config.fts_table} ON {config.table}.rowid = {config.fts_table}.rowid
    WHERE {' AND '.join(where_clauses)}
    ORDER BY {order_clause}
    LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    return sql, params


def build_index_sql(
    config: FTSConfig, uuid: str, values: dict[str, str], rowid: int | None = None
) -> tuple[str, list]:
    """Build INSERT SQL for FTS index with normalization applied.

    For external content FTS5 tables the rowid must match the content
    table's rowid. If not provided it is looked up from *values*.

    Args:
        config: FTS5 configuration
        uuid: Entry UUID
        values: Raw column values from main table
        rowid: Optional rowid (looked up from values if not provided)

    Returns:
        (sql, params) tuple
    """
    if rowid is None:
        rowid = values.get("rowid")

    norm_values = [rowid, uuid]  # rowid first, then uuid (UNINDEXED)
    for col in config.fts_columns:
        val = values.get(col, "")
        if col in config.normalize:
            val = config.normalize[col](val)
        norm_values.append(val)

    placeholders = ", ".join(["?"] * (len(config.fts_columns) + 2))
    sql = f"""
    INSERT INTO {config.fts_table} (rowid, uuid, {', '.join(config.fts_columns)})
    VALUES ({placeholders})
    """
    return sql, norm_values


__all__ = [
    "FTSConfig",
    "build_fts_schema",
    "build_search_query",
    "build_index_sql",
]