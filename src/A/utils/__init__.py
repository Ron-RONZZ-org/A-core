"""Utilities for A."""

from A.utils.output import info, success, warning, error, label, console
from A.utils.subprocess import run, has_command, SubprocessResult
from A.utils.editor import edit_text, edit_file
from A.utils.date import parse_partial_date, parse_partial_datetime
from A.utils.expr import eval_safe, validate_safe
from A.utils.clipboard import copy_to_clipboard, copy_file
from A.utils.serialize import serialize_json_columns, deserialize_json_columns
from A.utils.repl import ModuleREPL
from A.utils.deps import ensure_dependency, get_pip_command

__all__ = [
    "info",
    "success",
    "warning",
    "error",
    "label",
    "console",
    "run",
    "has_command",
    "SubprocessResult",
    "edit_text",
    "edit_file",
    "parse_partial_date",
    "parse_partial_datetime",
    "eval_safe",
    "validate_safe",
    "copy_to_clipboard",
    "copy_file",
    "serialize_json_columns",
    "deserialize_json_columns",
    "ensure_dependency",
    "get_pip_command",
]