# -*- coding: utf-8 -*-
"""A-core - minimal CLI framework."""

from A.core.i18n import tr, tr_multi
from A.core.paths import ensure_dirs
from A.core.exceptions import AError
from A.core.service import CRUDService, create_service
from A.core.undo import UndoManager, UndoOperation, create_undo_operation
from A.utils import info, success, warning, error, run
from A.utils.normalize import fold_search_text, normalize_french_ligatures, NORMALIZERS
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
    # Text normalization
    "fold_search_text",
    "normalize_french_ligatures",
    "NORMALIZERS",
    # Search
    "FTSConfig",
    # Undo system
    "UndoManager",
    "UndoOperation",
    "create_undo_operation",
]