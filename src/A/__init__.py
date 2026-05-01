# -*- coding: utf-8 -*-
"""A-core - minimal CLI framework."""

from A.core.i18n import tr
from A.core.paths import ensure_dirs
from A.core.exceptions import AError

__all__ = ["tr", "ensure_dirs", "AError"]