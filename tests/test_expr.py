"""Tests for A.utils.expr module."""

from __future__ import annotations

import pytest


class TestEvalSafe:
    """Tests for eval_safe."""

    def test_basic_arithmetic(self):
        from A.utils.expr import eval_safe

        assert eval_safe("2 + 2") == 4.0
        assert eval_safe("10 - 3") == 7.0
        assert eval_safe("4 * 5") == 20.0
        assert eval_safe("10 / 3") == pytest.approx(3.333, rel=1e-3)

    def test_operator_precedence(self):
        from A.utils.expr import eval_safe

        assert eval_safe("2 + 3 * 4") == 14.0
        assert eval_safe("(2 + 3) * 4") == 20.0
        assert eval_safe("10 / 2 + 3") == 8.0

    def test_floor_div_and_mod(self):
        from A.utils.expr import eval_safe

        assert eval_safe("10 // 3") == 3.0
        assert eval_safe("10 % 3") == 1.0

    def test_power(self):
        from A.utils.expr import eval_safe

        assert eval_safe("2 ** 3") == 8.0
        assert eval_safe("2 ** 0.5") == pytest.approx(1.414, rel=1e-3)

    def test_unary_operators(self):
        from A.utils.expr import eval_safe

        assert eval_safe("-5") == -5.0
        assert eval_safe("+5") == 5.0
        assert eval_safe("-(2 + 3)") == -5.0

    def test_float_literals(self):
        from A.utils.expr import eval_safe

        assert eval_safe("3.14") == 3.14
        assert eval_safe(".5") == 0.5

    def test_with_variables(self):
        from A.utils.expr import eval_safe

        assert eval_safe("D", {"D": 5}) == 5.0
        assert eval_safe("20 + 2 * D", {"D": 5}) == 30.0
        assert eval_safe("H * 60 + M", {"H": 2, "M": 30}) == 150.0

    def test_default_functions(self):
        from A.utils.expr import eval_safe

        assert eval_safe("min(10, 20)") == 10.0
        assert eval_safe("max(10, 20)") == 20.0
        assert eval_safe("abs(-5)") == 5.0
        assert eval_safe("round(3.7)") == 4.0
        assert eval_safe("int(3.7)") == 3.0
        assert eval_safe("float(5)") == 5.0

    def test_custom_functions(self):
        from A.utils.expr import eval_safe

        def clamp(value, lo, hi):
            return max(lo, min(hi, value))

        assert eval_safe("clamp(x, 0, 100)", {"x": 150}, {"clamp": clamp}) == 100.0
        assert eval_safe("clamp(x, 0, 100)", {"x": -10}, {"clamp": clamp}) == 0.0

    def test_nested_functions(self):
        from A.utils.expr import eval_safe

        result = eval_safe("min(max(10, 20), 15)")
        assert result == 15.0

    def test_nested_with_vars(self):
        from A.utils.expr import eval_safe

        result = eval_safe("min(20 + 2 * D, 70)", {"D": 30})
        assert result == 70.0  # 20 + 60 = 80, but min caps at 70

    def test_real_world_priority(self):
        """Realistic priority formula from autish-legacy."""
        from A.utils.expr import eval_safe

        # "20 + 2 * D" where D = days since creation (e.g. 5 days)
        result = eval_safe("20 + 2 * D", {"D": 5})
        assert result == 30.0

        # "min(30, 10 * H)" where H = hours since creation
        result = eval_safe("min(30, 10 * H)", {"H": 4})
        assert result == 30.0  # 10 * 4 = 40, capped at 30

    def test_empty_expression_raises(self):
        from A.utils.expr import eval_safe

        with pytest.raises(ValueError, match="cannot be empty"):
            eval_safe("")

    def test_whitespace_only_raises(self):
        from A.utils.expr import eval_safe

        with pytest.raises(ValueError, match="cannot be empty"):
            eval_safe("   ")

    def test_simple_number(self):
        """Plain number is valid."""
        from A.utils.expr import eval_safe

        assert eval_safe("42") == 42.0

    def test_unsafe_import_raises(self):
        """__import__ is not allowed."""
        from A.utils.expr import eval_safe

        with pytest.raises(ValueError, match="not allowed"):
            eval_safe('__import__("os")')

    def test_unsafe_call_raises(self):
        """Unknown function names are rejected."""
        from A.utils.expr import eval_safe

        with pytest.raises(ValueError, match="not allowed"):
            eval_safe("open('/etc/passwd')")

    def test_unknown_variable_raises(self):
        """Unknown variable names are rejected."""
        from A.utils.expr import eval_safe

        with pytest.raises(ValueError, match="not allowed"):
            eval_safe("unknown_var + 1")

    def test_attribute_access_raises(self):
        """Attribute access (obj.attr) is rejected."""
        from A.utils.expr import eval_safe

        with pytest.raises(ValueError):
            eval_safe("os.system('ls')")

    def test_list_comprehension_raises(self):
        """List comprehensions are rejected."""
        from A.utils.expr import eval_safe

        with pytest.raises((ValueError, SyntaxError)):
            eval_safe("[x for x in range(10)]")

    def test_lambda_raises(self):
        """Lambda expressions are rejected."""
        from A.utils.expr import eval_safe

        with pytest.raises((ValueError, SyntaxError)):
            eval_safe("lambda x: x + 1")

    def test_inf_and_nan_are_not_allowed(self):
        """Infinity and NaN in result are rejected."""
        from A.utils.expr import eval_safe

        with pytest.raises(ValueError, match="division by zero"):
            eval_safe("1 / 0")

    def test_none_returns_default(self):
        """None input raises."""
        from A.utils.expr import eval_safe

        with pytest.raises(ValueError):
            eval_safe(None)


class TestValidateSafe:
    """Tests for validate_safe."""

    def test_valid_expression(self):
        from A.utils.expr import validate_safe

        assert validate_safe("2 + 2") is True
        assert validate_safe("min(10, 20)") is True

    def test_invalid_syntax(self):
        from A.utils.expr import validate_safe

        assert validate_safe("2 +") is False

    def test_unsafe_expression(self):
        from A.utils.expr import validate_safe

        assert validate_safe("__import__('os')") is False

    def test_empty(self):
        from A.utils.expr import validate_safe

        assert validate_safe("") is False

    def test_with_allowed_vars(self):
        from A.utils.expr import validate_safe

        # D is not in default allowed set, so this should fail
        assert validate_safe("20 + 2 * D") is False
        # D is explicitly allowed
        assert validate_safe("20 + 2 * D", allowed_vars={"D"}) is True
        assert validate_safe("min(30, 10 * H)", allowed_vars={"H"}) is True
        assert validate_safe("M + D + H + m", allowed_vars={"M", "D", "H", "m"}) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
