"""Safe mathematical expression evaluator.

Provides ``eval_safe()`` for evaluating user-provided math expressions
without risk of arbitrary code execution. Uses AST-based sandboxing
to restrict which operations, functions, and variables are allowed.

Ported from autish-legacy todo.py priority formula engine.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Callable
from typing import Any

# Default set of allowed AST node types for safe expressions.
_ALLOWED_NODES: tuple[type[ast.AST], ...] = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Name,
    ast.Call,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
)

# Default allowed function names and their implementations.
_DEFAULT_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "int": int,
    "float": float,
}


def eval_safe(
    expression: str,
    variables: dict[str, float] | None = None,
    functions: dict[str, Callable[..., Any]] | None = None,
) -> float:
    """Evaluate a safe mathematical expression string.

    Parses the expression using Python's AST, validates every node
    against a whitelist of safe operations, then evaluates with
    restricted globals (no ``__builtins__``).

    Args:
        expression: Math expression string.
            Example: ``"min(20 + 2 * D, 70)"``
        variables: Variable name to value mapping.
            Example: ``{"D": 5.0, "H": 2.0}``
        functions: Additional or replacement functions.
            Defaults to ``min``, ``max``, ``abs``, ``round``, ``int``, ``float``.
            Pass ``{}`` to disable defaults.

    Returns:
        Computed float result.

    Raises:
        ValueError: If the expression is empty, contains unsafe nodes,
                    references unknown names, or produces a non-finite result.
    """
    text = str(expression or "").strip()
    if not text:
        raise ValueError("Expression cannot be empty.")

    # Try direct numeric parse first (fast path)
    try:
        return float(text)
    except ValueError:
        pass

    # Parse AST
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid expression syntax: {exc}") from exc

    # Validate AST nodes
    _assert_safe_expr(tree, variables or {}, functions or _DEFAULT_FUNCTIONS)

    # Build safe evaluation context
    merged_functions = {**_DEFAULT_FUNCTIONS, **(functions or {})}
    safe_locals: dict[str, Any] = {}
    safe_locals.update(merged_functions)
    if variables:
        safe_locals.update(variables)

    # Evaluate with builtins locked down
    try:
        result = eval(
            compile(tree, "<eval_safe>", "eval"),
            {"__builtins__": {}},
            safe_locals,
        )
    except (ZeroDivisionError, OverflowError, ValueError) as exc:
        raise ValueError(f"Expression error: {exc}") from exc

    if not isinstance(result, (int, float)):
        raise ValueError(
            f"Expression did not return a number, got {type(result).__name__}."
        )
    if not math.isfinite(float(result)):
        raise ValueError("Expression returned a non-finite value (inf or nan).")

    return float(result)


def _assert_safe_expr(
    tree: ast.AST,
    allowed_vars: dict[str, Any],
    allowed_funcs: dict[str, Any],
) -> None:
    """Walk the AST and verify every node is safe.

    Args:
        tree: Parsed AST.
        allowed_vars: Dict of allowed variable names.
        allowed_funcs: Dict of allowed function names.

    Raises:
        ValueError: If an unsafe node, function, or variable is found.
    """
    allowed_var_names = set(allowed_vars.keys())
    allowed_func_names = set(allowed_funcs.keys())
    # Variable names may overlap with function names (e.g. "min" as both);
    # ensure both sets are allowed.
    all_allowed_names = allowed_var_names | allowed_func_names

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(
                f"Unsafe expression: {type(node).__name__} is not allowed."
            )

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls are allowed.")
            if node.func.id not in allowed_func_names:
                raise ValueError(
                    f"Function '{node.func.id}' is not allowed. "
                    f"Allowed: {', '.join(sorted(allowed_func_names))}"
                )

        if isinstance(node, ast.Name):
            if node.id not in all_allowed_names and node.id != "_":
                raise ValueError(
                    f"Variable '{node.id}' is not allowed. "
                    f"Allowed: {', '.join(sorted(all_allowed_names))}"
                )


def validate_safe(
    expression: str,
    allowed_vars: set[str] | None = None,
) -> bool:
    """Check whether an expression is syntactically and structurally safe.

    This is a lightweight check that parses and validates the AST
    without evaluating. Useful for input validation before storage.

    Args:
        expression: Math expression string.
        allowed_vars: Optional set of additional allowed variable names
                      beyond the default function names.

    Returns:
        True if the expression is safe, False otherwise.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        # Build allowed vars including both functions and extra variables
        allowed = dict.fromkeys(_DEFAULT_FUNCTIONS)
        if allowed_vars:
            allowed.update(dict.fromkeys(allowed_vars))
        _assert_safe_expr(tree, allowed, _DEFAULT_FUNCTIONS)
        return True
    except (ValueError, SyntaxError):
        return False


__all__ = [
    "eval_safe",
    "validate_safe",
]
