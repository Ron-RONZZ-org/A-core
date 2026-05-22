"""Tests for A.core.wikidata — API client, common properties, language helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from A.core.wikidata import (
    COMMON_PROPERTIES,
    get_common_properties,
    get_property_details,
    get_property_metadata,
    search_languages,
    search_properties,
)
from A.core.wikidata._client import (
    _api_get,
    _extract_all_language_metadata,
    _extract_entity_metadata,
    _language_priority,
    _properties_details,
    _properties_metadata,
)


# ── Language resolution ───────────────────────────────────────────────────────


class TestLanguagePriority:
    def test_eo_fallback(self) -> None:
        assert _language_priority(["en"]) == ["en", "eo"]

    def test_eo_already_present(self) -> None:
        assert _language_priority(["eo", "en"]) == ["eo", "en"]

    def test_deduplicates_and_appends_fallback(self) -> None:
        assert _language_priority(["en", "en", "fr"]) == ["en", "fr", "eo"]


class TestSearchLanguages:
    def test_none_uses_env(self) -> None:
        langs = search_languages(None)
        assert isinstance(langs, list)
        assert len(langs) >= 1

    def test_single_code(self) -> None:
        langs = search_languages("fr")
        assert langs[0] == "fr"

    def test_multiple_codes(self) -> None:
        langs = search_languages("de,fr")
        assert langs[0] == "de"
        assert langs[1] == "fr"

    def test_invalid_code_raises(self) -> None:
        with pytest.raises(ValueError, match="lingvo"):
            search_languages("toolong")


# ── Entity metadata extraction ────────────────────────────────────────────────


class TestExtractEntityMetadata:
    def test_extracts_label_and_description(self) -> None:
        entity = {
            "labels": {"en": {"value": "Population"}},
            "descriptions": {"en": {"value": "number of inhabitants"}},
            "aliases": {"en": [{"value": "pop"}]},
        }
        result = _extract_entity_metadata(entity, prop_id="P1082", lang_list=["en", "eo"])
        assert result["etikedo"] == "Population"
        assert result["priskribo"] == "number of inhabitants"
        assert "pop" in result["aliasoj"]
        assert "p1082" in [a.lower() for a in result["aliasoj"]]

    def test_prefers_first_language(self) -> None:
        entity = {
            "labels": {"eo": {"value": "Loĝantaro"}, "en": {"value": "Population"}},
            "descriptions": {"eo": {"value": "Nombro da loĝantoj"}},
            "aliases": {},
        }
        result = _extract_entity_metadata(entity, prop_id="P1082", lang_list=["eo", "en"])
        assert result["etikedo"] == "Loĝantaro"

    def test_handles_empty_entity(self) -> None:
        result = _extract_entity_metadata({}, prop_id="P1", lang_list=["en"])
        assert result["etikedo"] == ""
        assert result["priskribo"] == ""
        # prop_id always added as alias
        assert "p1" in [a.lower() for a in result["aliasoj"]]


# ── Common properties ─────────────────────────────────────────────────────────


class TestCommonProperties:
    def test_has_population(self) -> None:
        assert "population" in COMMON_PROPERTIES
        assert COMMON_PROPERTIES["population"][0]["id"] == "P1082"

    def test_get_common_properties_returns_copy(self) -> None:
        result = get_common_properties()
        assert result is not COMMON_PROPERTIES  # different object
        assert result["population"] == COMMON_PROPERTIES["population"]


# ── Wikidata API client (mocked) ──────────────────────────────────────────────


class TestApiGet:
    @patch("A.core.wikidata._client.urllib.request.urlopen")
    def test_success(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.headers.get_content_charset.return_value = "utf-8"
        mock_response.read.return_value = b'{"entities":{"P1082":{}}}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = _api_get({"action": "wbgetentities", "ids": "P1082"})
        assert result == {"entities": {"P1082": {}}}

    @patch("A.core.wikidata._client.urllib.request.urlopen")
    def test_invalid_json_raises(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.headers.get_content_charset.return_value = "utf-8"
        mock_response.read.return_value = b"not json"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(RuntimeError, match="respondo"):
            _api_get({"action": "test"})

    @patch("A.core.wikidata._client.urllib.request.urlopen")
    def test_timeout_raises(self, mock_urlopen: MagicMock) -> None:
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("timeout")

        with pytest.raises(RuntimeError, match="neatingebla"):
            _api_get({"action": "test"})


class TestSearchPropertiesMocked:
    @patch("A.core.wikidata._client._api_get")
    def test_returns_results(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {
            "search": [
                {
                    "id": "P1082",
                    "label": "population",
                    "description": "number of inhabitants",
                    "match": {"text": "pop"},
                },
            ]
        }

        results = search_properties("population", languages=["en"])
        assert len(results) >= 1
        # The metadata enrichment call may return empty, but basic data is there
        assert any("wdt:P1082" in r.get("ligilo", "") for r in results)

    @patch("A.core.wikidata._client._api_get")
    def test_no_results(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"search": []}
        results = search_properties("xyzzy_nonexistent", languages=["en"])
        assert results == []

    @patch("A.core.wikidata._client._api_get")
    def test_invalid_search_response(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {}
        results = search_properties("test", languages=["en"])
        assert results == []


class TestGetPropertyMetadataMocked:
    @patch("A.core.wikidata._client._api_get")
    def test_returns_metadata(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {
            "entities": {
                "P1082": {
                    "labels": {"en": {"value": "population"}},
                    "descriptions": {"en": {"value": "number of inhabitants"}},
                    "aliases": {"en": [{"value": "pop"}]},
                },
            },
        }
        result = get_property_metadata("P1082", languages=["en"])
        assert result["etikedo"] == "population"
        assert result["priskribo"] == "number of inhabitants"

    @patch("A.core.wikidata._client._api_get")
    def test_missing_entity_raises(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"entities": {}}
        with pytest.raises(RuntimeError):
            get_property_metadata("P999999", languages=["en"])


class TestPropertiesMetadataMocked:
    @patch("A.core.wikidata._client._api_get")
    def test_fetches_multiple(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {
            "entities": {
                "P31": {
                    "labels": {"en": {"value": "instance of"}},
                    "descriptions": {},
                    "aliases": {},
                },
                "P279": {
                    "labels": {"en": {"value": "subclass of"}},
                    "descriptions": {},
                    "aliases": {},
                },
            },
        }
        result = _properties_metadata(["P31", "P279"], languages=["en"])
        assert "P31" in result
        assert "P279" in result
        assert result["P31"]["etikedo"] == "instance of"

    @patch("A.core.wikidata._client._api_get")
    def test_empty_ids(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {}
        result = _properties_metadata([], languages=["en"])
        assert result == {}
        mock_api.assert_not_called()


# ── Per-language extraction ──────────────────────────────────────────────────


class TestExtractAllLanguageMetadata:
    def test_returns_per_language_labels(self) -> None:
        entity = {
            "labels": {"en": {"value": "Population"}, "eo": {"value": "Loĝantaro"}},
            "descriptions": {"en": {"value": "number of inhabitants"}},
            "aliases": {"en": [{"value": "pop"}], "eo": [{"value": "loĝantaroj"}]},
        }
        result = _extract_all_language_metadata(entity, prop_id="P1082")
        assert result["labels"]["en"] == "Population"
        assert result["labels"]["eo"] == "Loĝantaro"
        assert result["descriptions"]["en"] == "number of inhabitants"
        assert "pop" in result["aliases"]["en"]
        assert "loĝantaroj" in result["aliases"]["eo"]

    def test_prop_id_in_each_language_aliases(self) -> None:
        entity = {
            "labels": {"en": {"value": "Population"}},
            "descriptions": {},
            "aliases": {"en": [{"value": "pop"}], "eo": [{"value": "loĝantaroj"}]},
        }
        result = _extract_all_language_metadata(entity, prop_id="P1082")
        assert "p1082" in [a.lower() for a in result["aliases"]["en"]]
        assert "p1082" in [a.lower() for a in result["aliases"]["eo"]]

    def test_seeds_alias_when_none_exist(self) -> None:
        entity = {
            "labels": {"en": {"value": "Population"}},
            "descriptions": {},
            "aliases": {},
        }
        result = _extract_all_language_metadata(entity, prop_id="P1082")
        # Should seed "en" (the only language with labels) with prop_id
        assert result["aliases"] == {"en": ["p1082"]}

    def test_empty_entity(self) -> None:
        result = _extract_all_language_metadata({}, prop_id="P1")
        assert result["labels"] == {}
        assert result["descriptions"] == {}
        assert result["aliases"] == {"en": ["p1"]}

    def test_handles_missing_keys(self) -> None:
        result = _extract_all_language_metadata(
            {"labels": None, "descriptions": None, "aliases": None},
            prop_id="P1",
        )
        assert result["labels"] == {}
        assert result["descriptions"] == {}


# ── get_property_details (mocked) ────────────────────────────────────────────


class TestGetPropertyDetailsMocked:
    @patch("A.core.wikidata._client._api_get")
    def test_returns_per_language_data(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {
            "entities": {
                "P1082": {
                    "labels": {
                        "en": {"value": "population"},
                        "eo": {"value": "loĝantaro"},
                    },
                    "descriptions": {
                        "en": {"value": "number of inhabitants"},
                        "eo": {"value": "nombro da loĝantoj"},
                    },
                    "aliases": {
                        "en": [{"value": "pop"}],
                        "eo": [{"value": "loĝantaroj"}],
                    },
                },
            },
        }
        result = get_property_details("P1082", languages=["en", "eo"])
        assert result["id"] == "P1082"
        assert result["labels"]["en"] == "population"
        assert result["labels"]["eo"] == "loĝantaro"
        assert result["descriptions"]["eo"] == "nombro da loĝantoj"
        assert result["aliases"]["en"] == ["pop", "p1082"]
        assert result["aliases"]["eo"] == ["loĝantaroj", "p1082"]

    @patch("A.core.wikidata._client._api_get")
    def test_missing_entity_raises(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {"entities": {}}
        with pytest.raises(RuntimeError):
            get_property_details("P999999", languages=["en"])

    @patch("A.core.wikidata._client._api_get")
    def test_single_language(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {
            "entities": {
                "P31": {
                    "labels": {"en": {"value": "instance of"}},
                    "descriptions": {},
                    "aliases": {},
                },
            },
        }
        result = get_property_details("P31", languages=["en"])
        assert result["labels"]["en"] == "instance of"
        assert "en" not in result.get("descriptions", {})


# ── _properties_details (mocked) ─────────────────────────────────────────────


class TestPropertiesDetailsMocked:
    @patch("A.core.wikidata._client._api_get")
    def test_fetches_multiple(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {
            "entities": {
                "P31": {
                    "labels": {
                        "en": {"value": "instance of"},
                        "eo": {"value": "estas ekzemplo de"},
                    },
                    "descriptions": {},
                    "aliases": {},
                },
                "P279": {
                    "labels": {
                        "en": {"value": "subclass of"},
                        "eo": {"value": "subklaso de"},
                    },
                    "descriptions": {},
                    "aliases": {},
                },
            },
        }
        result = _properties_details(["P31", "P279"], languages=["en", "eo"])
        assert "P31" in result
        assert "P279" in result
        assert result["P31"]["labels"]["en"] == "instance of"
        assert result["P31"]["labels"]["eo"] == "estas ekzemplo de"
        assert result["P279"]["labels"]["eo"] == "subklaso de"

    @patch("A.core.wikidata._client._api_get")
    def test_empty_ids(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {}
        result = _properties_details([], languages=["en"])
        assert result == {}
        mock_api.assert_not_called()

    @patch("A.core.wikidata._client._api_get")
    def test_handles_partial_results(self, mock_api: MagicMock) -> None:
        mock_api.return_value = {
            "entities": {
                "P31": {
                    "labels": {"en": {"value": "instance of"}},
                    "descriptions": {},
                    "aliases": {},
                },
            },
        }
        # P279 is missing from the API response
        result = _properties_details(["P31", "P279"], languages=["en"])
        assert "P31" in result
        assert "P279" not in result


# ── Integration-style (no network) ───────────────────────────────────────────


def test_search_languages_invalid_code_raises() -> None:
    with pytest.raises(ValueError):
        search_languages("xyz")


def test_get_common_properties_contains_population() -> None:
    common = get_common_properties()
    assert "population" in common
    assert common["population"][0]["id"] == "P1082"
