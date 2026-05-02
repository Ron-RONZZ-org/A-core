# -*- coding: utf-8 -*-
"""A-core - minimal CLI framework."""

from A.core.i18n import tr
from A.core.paths import ensure_dirs
from A.core.exceptions import AError
from A.core.service import CRUDService, create_service
from A.utils import info, success, warning, error, run

__all__ = [
    "tr", 
    "ensure_dirs", 
    "AError", 
    "CRUDService",
    "create_service",
    "info", 
    "success", 
    "warning", 
    "error", 
    "run",
]