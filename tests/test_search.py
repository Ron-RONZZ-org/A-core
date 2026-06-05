"""Tests for A.data.search — FTSConfig, build_fts_schema, build_search_query."""

from __future__ import annotations

import pytest

from A.data.search import FTSConfig, build_fts_schema, build_search_query


def _make_config() -> FTSConfig:
    return FTSConfig(
        table="vorto",
        fts_columns=["teksto"],
        filter_columns=["lingvo", "kategorio", "tipo", "temo"],
    )


class TestFTSConfig:
    """Tests for FTSConfig construction and defaults."""

    def test_default_fts_table_name(self):
        """fts_table defaults to {table}_fts."""
        config = _make_config()
        assert config.fts_table == "vorto_fts"

    def test_custom_fts_table_name(self):
        """Custom fts_table is honoured."""
        config = FTSConfig(table="vorto", fts_columns=["teksto"], fts_table="my_fts")
        assert config.fts_table == "my_fts"

    def test_default_normalize(self):
        """Normalize defaults to fold_search_text for FTS columns."""
        config = _make_config()
        assert "teksto" in config.normalize


class TestBuildFtsSchema:
    """Tests for build_fts_schema."""

    def test_returns_list_of_statements(self):
        """Returns a list of SQL statements."""
        config = _make_config()
        stmts = build_fts_schema(config)
        assert isinstance(stmts, list)
        assert len(stmts) > 0

    def test_creates_fts_table(self):
        """First statement creates FTS virtual table."""
        config = _make_config()
        stmts = build_fts_schema(config)
        assert "CREATE VIRTUAL TABLE" in stmts[0]
        assert config.fts_table in stmts[0]

    def test_creates_filter_indexes(self):
        """Creates indexes for each filter column."""
        config = _make_config()
        stmts = build_fts_schema(config)
        index_count = sum(1 for s in stmts if "CREATE INDEX" in s)
        assert index_count == len(config.filter_columns)


class TestBuildSearchQuery:
    """Tests for build_search_query."""

    def test_basic_query(self):
        """Basic query generates FTS5 MATCH clause."""
        config = _make_config()
        sql, params = build_search_query(config, "hello")
        assert "MATCH ?" in sql
        assert params[0] == '"hello"*'

    def test_with_exact_filters(self):
        """Exact match filters add WHERE clauses."""
        config = _make_config()
        sql, params = build_search_query(config, "hello", filters={"lingvo": "fr"})
        assert "vorto.lingvo = ?" in sql
        assert "fr" in params

    def test_with_range_filters_both(self):
        """Both bounds add WHERE >= and <= clauses."""
        config = _make_config()
        sql, params = build_search_query(
            config,
            "hello",
            range_filters={"kreita_je": ("2026-01-01T00:00:00+00:00", "2026-12-31T23:59:59+00:00")},
        )
        assert "vorto.kreita_je >= ?" in sql
        assert "vorto.kreita_je <= ?" in sql
        assert "2026-01-01T00:00:00+00:00" in params
        assert "2026-12-31T23:59:59+00:00" in params

    def test_with_range_filters_start_only(self):
        """Start-only range adds only >= clause."""
        config = _make_config()
        sql, params = build_search_query(
            config,
            "hello",
            range_filters={"kreita_je": ("2026-01-01T00:00:00+00:00", None)},
        )
        assert "vorto.kreita_je >= ?" in sql
        assert "vorto.kreita_je <= ?" not in sql

    def test_with_range_filters_end_only(self):
        """End-only range adds only <= clause."""
        config = _make_config()
        sql, params = build_search_query(
            config,
            "hello",
            range_filters={"kreita_je": (None, "2026-12-31T23:59:59+00:00")},
        )
        assert "vorto.kreita_je <= ?" in sql
        assert "vorto.kreita_je >= ?" not in sql

    def test_range_filters_empty_dict(self):
        """Empty range_filters dict is a no-op."""
        config = _make_config()
        sql1, _ = build_search_query(config, "hello", range_filters={})
        sql2, _ = build_search_query(config, "hello")
        assert sql1 == sql2

    def test_combined_filters_and_range_filters(self):
        """Filters and range_filters work together."""
        config = _make_config()
        sql, params = build_search_query(
            config,
            "hello",
            filters={"lingvo": "fr"},
            range_filters={"kreita_je": ("2026-01-01T00:00:00+00:00", "2026-12-31T23:59:59+00:00")},
        )
        assert "vorto.lingvo = ?" in sql
        assert "vorto.kreita_je >= ?" in sql
        assert "vorto.kreita_je <= ?" in sql

    def test_limit_and_offset(self):
        """LIMIT and OFFSET are appended."""
        config = _make_config()
        sql, params = build_search_query(config, "hello", limit=10, offset=5)
        assert "LIMIT ? OFFSET ?" in sql
        assert 10 in params
        assert 5 in params

    def test_order_by_relevance(self):
        """Default ordering is by rank (BM25)."""
        config = _make_config()
        sql, _ = build_search_query(config, "hello")
        assert "ORDER BY rank" in sql

    def test_order_by_date(self):
        """Order by date uses kreita_je DESC."""
        config = _make_config()
        sql, _ = build_search_query(config, "hello", order_by="date")
        assert "ORDER BY vorto.kreita_je DESC" in sql

    def test_order_by_column(self):
        """Order by column name."""
        config = _make_config()
        sql, _ = build_search_query(config, "hello", order_by="teksto")
        assert "ORDER BY vorto.teksto" in sql

    def test_empty_query_with_range_filters(self):
        """Empty query with range_filters skips FTS MATCH clause."""
        config = _make_config()
        sql, params = build_search_query(
            config,
            "",
            range_filters={"kreita_je": ("2026-01-01T00:00:00+00:00", None)},
        )
        assert "MATCH" not in sql
        assert "kreita_je >= ?" in sql
        assert "2026-01-01T00:00:00+00:00" in params

    def test_empty_query_with_filters(self):
        """Empty query with exact filters skips FTS MATCH."""
        config = _make_config()
        sql, params = build_search_query(
            config,
            "",
            filters={"lingvo": "fr"},
        )
        assert "MATCH" not in sql
        assert "vorto.lingvo = ?" in sql
        assert "fr" in params

    def test_empty_query_no_filters_no_where(self):
        """Fully empty query+no filters produces no WHERE clause."""
        config = _make_config()
        sql, _ = build_search_query(config, "")
        assert "WHERE" not in sql.upper() or "WHERE \n" in sql
