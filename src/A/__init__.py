# -*- coding: utf-8 -*-
"""A-core - minimal CLI framework."""

from A.core.i18n import tr, tr_multi
from A.core.paths import ensure_dirs
from A.core.exceptions import AError
from A.core.service import CRUDService, create_service
from A.core.undo import UndoManager, UndoOperation, create_undo_operation
from A.core.links import Link, get_links_db, add_link, remove_link, get_outgoing, get_incoming, get_links, bulk_add_links
from A.core.references import Ref, ResolvedRef, parse_refs, resolve, get_ref_display, clear_ref_cache
from A.core.ai import get_provider, save_api_key, get_api_key
from A.core.registry import fetch_registry, search_registry, get_module_info, get_installed_modules
from A.core.backup_targets import BackupTarget, get_backup_targets, clear_cache as clear_backup_cache
from A.core.providers import LLMProvider, ToolCall, LLMResponse
from A.utils import info, success, warning, error, run, copy_to_clipboard, copy_file, serialize_json_columns, deserialize_json_columns
from A.utils.interactive import select_candidate, select_candidates, confirm_action
from A.utils.normalize import fold_search_text, normalize_french_ligatures, NORMALIZERS
from A.core.markdown_parser import render_markdown
from A.core.markdown_html_view import preview_markdown, preview_html, clear_cache
from A.data.search import FTSConfig

__all__ = [
    "tr",
    "tr_multi",
    "ensure_dirs",
    "AError",
    "CRUDService",
    "create_service",
    "info",
    "success",
    "warning",
    "error",
    "run",
    "copy_to_clipboard",
    "copy_file",
    "serialize_json_columns",
    "deserialize_json_columns",
    # Text normalization
    "fold_search_text",
    "normalize_french_ligatures",
    "NORMALIZERS",
    # Markdown rendering
    "render_markdown",
    "preview_markdown",
    "preview_html",
    "clear_cache",
    # Search
    "FTSConfig",
    # Undo system
    "UndoManager",
    "UndoOperation",
    "create_undo_operation",
    # Module registry
    "fetch_registry",
    "search_registry",
    "get_module_info",
    "get_installed_modules",
    # Interactive selection
    "select_candidate",
    "confirm_action",
    # Backup
    "BackupTarget",
    "get_backup_targets",
    "clear_backup_cache",
    # Links (bidirectional)
    "Link",
    "get_links_db",
    "add_link",
    "remove_link",
    "bulk_add_links",
    "get_outgoing",
    "get_incoming",
    "get_links",
    # References (vt#uuid, ec#uuid)
    "Ref",
    "ResolvedRef",
    "parse_refs",
    "resolve",
    "get_ref_display",
    "clear_ref_cache",
    # AI / LLM providers
    "get_provider",
    "save_api_key",
    "get_api_key",
    "LLMProvider",
    "ToolCall",
    "LLMResponse",
]
