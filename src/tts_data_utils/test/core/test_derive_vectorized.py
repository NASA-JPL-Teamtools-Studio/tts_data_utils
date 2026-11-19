from datetime import datetime, timedelta

import pandas as pd
import pytest

import tts_data_utils.core.data_frame as data_frame_module
from tts_data_utils.core.data_frame import TtsDataFrame
from tts_data_utils.core.expr_engines import _MathTransformer


def _frame(cls=TtsDataFrame, n=6, zero_b_at=None, int_values=False):
    t0 = datetime(2020, 1, 1)
    rows = []
    for i in range(n):
        t = t0 + timedelta(seconds=i)
        a = int(i + 1) if int_values else float(i + 1)
        b = 0.0 if i == zero_b_at else float((i + 1) * 2)
        rows.append({"time": t, "label": "a", "value": a})
        rows.append({"time": t, "label": "b", "value": b})
    return cls(rows, coerce=False, validate=False)


_KW = dict(index_col="time", label_col="label", value_col="value")


def _run(frame, expr, timeout, vectorized, monkeypatch):
    monkeypatch.setattr(data_frame_module, "_VECTORIZE_DERIVATIONS", vectorized)
    try:
        return frame.derive_values(expr, timeout=timeout, **_KW).reset_index(drop=True)
    except Exception as exc:
        return exc


_PARITY_EXPRS = [
    "d = a * 2 - abs(b)",
    "d = a / b",
    "d = a // 2",
    "d = a ** 2",
    "d = a ** -1",
    "d = sqrt(a)",
    "d = floor(a / 3)",
    "d = poly(1.0, 2.0, 3.0, a)",
    "d = poly(1.0, 2.0, a) + b",
    "d = a > b",
    "d = a > 1 and b < 11",
    "d = a or b",
    "d = not (a > 2)",
    "d = a in [1.0, 3.0]",
    "d = a in [1, 3] and b > 2",
    "d = 2 * exp(a / 10)",
    "d = a > 1 and b",
    "d = a > 1 or b",
    "d = a and b",
    "d = (a > 1) * (b > 2)",
    "d = -(a > 1)",
    "d = (a > 1) + 1",
    "d = a > 1 and b > 2",
    "d = a and 2",
    "d = a > 1 or 0",
]


@pytest.mark.unreviewed_ai_generated_test
@pytest.mark.parametrize("timeout", [0, timedelta(seconds=5)])
@pytest.mark.parametrize("expr", _PARITY_EXPRS)
def test_vectorized_matches_scalar(expr, timeout, monkeypatch):
    frame = _frame()
    vec = _run(frame, expr, timeout, True, monkeypatch)
    ref = _run(frame, expr, timeout, False, monkeypatch)

    assert not isinstance(ref, Exception)
    pd.testing.assert_frame_equal(vec, ref, check_exact=False, rtol=1e-12, atol=0)


@pytest.mark.unreviewed_ai_generated_test
@pytest.mark.parametrize("vectorized", [True, False])
def test_division_by_zero_raises_the_same_error_on_both_paths(vectorized, monkeypatch):
    frame = _frame(zero_b_at=2)

    result = _run(frame, "d = a / b", 0, vectorized, monkeypatch)

    assert isinstance(result, ZeroDivisionError)


@pytest.mark.unreviewed_ai_generated_test
def test_plain_expression_never_computes_derivation_context(monkeypatch):
    calls = []

    class _CountingFrame(TtsDataFrame):
        def get_derivation_context(self, timestamp, values):
            calls.append(timestamp)
            return {}

    frame = _frame(cls=_CountingFrame)

    _run(frame, "d = a * b", 0, True, monkeypatch)

    assert calls == []


class _CtxTransformer(_MathTransformer):
    def __init__(self, values, context=None):
        super().__init__(values, context=context)
        self._FUNCS = {**self._FUNCS, "ctx": lambda x: x + self._context["k"]}


class _PairTransformer(_MathTransformer):
    def __init__(self, values, context=None):
        super().__init__(values, context=context)
        self._FUNCS = {**self._FUNCS, "pair": lambda x, y: [x * 2, y + 1]}


@pytest.mark.unreviewed_ai_generated_test
def test_context_is_computed_only_when_a_function_reads_it(monkeypatch):
    calls = []

    class _CtxFrame(TtsDataFrame):
        MATH_TRANSFORMER = _CtxTransformer

        def get_derivation_context(self, timestamp, values):
            calls.append(timestamp)
            return {"k": 10.0}

    frame = _frame(cls=_CtxFrame)

    out = _run(frame, "d = ctx(a)", 0, True, monkeypatch)

    assert len(calls) == 6
    assert out[out["label"] == "d"]["value"].tolist() == [11.0, 12.0, 13.0, 14.0, 15.0, 16.0]


class _PairFrame(TtsDataFrame):
    MATH_TRANSFORMER = _PairTransformer


@pytest.mark.unreviewed_ai_generated_test
def test_multi_target_assignment_matches_scalar(monkeypatch):
    frame = _frame(cls=_PairFrame)
    expr = "x, y = pair(a, b)"

    vec = _run(frame, expr, 0, True, monkeypatch)
    ref = _run(frame, expr, 0, False, monkeypatch)

    assert not isinstance(ref, Exception)
    pd.testing.assert_frame_equal(vec, ref, check_exact=False, rtol=1e-12, atol=0)
    assert set(vec["label"]) == {"x", "y"}


def _counting_twice(counter):
    def scalar(x):
        counter.append(x)
        return x * 2

    return scalar


@pytest.mark.unreviewed_ai_generated_test
def test_registered_vector_impl_runs_once_per_expression(monkeypatch):
    counter = []
    scalar = _counting_twice(counter)

    class _RegisteredTransformer(_MathTransformer):
        _FUNCS = {**_MathTransformer._FUNCS, "twice": scalar}
        _VECTOR_IMPL = {**_MathTransformer._VECTOR_IMPL, "twice": (scalar, lambda x: x * 2)}

    class _RegisteredFrame(TtsDataFrame):
        MATH_TRANSFORMER = _RegisteredTransformer

    frame = _frame(cls=_RegisteredFrame)
    out = _run(frame, "d = twice(a)", 0, True, monkeypatch)

    assert not isinstance(out, Exception)
    assert len(counter) == 0
    assert out[out["label"] == "d"]["value"].tolist() == [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]


@pytest.mark.unreviewed_ai_generated_test
def test_overridden_function_falls_back_to_scalar(monkeypatch):
    counter = []
    scalar = _counting_twice(counter)

    class _OverriddenTransformer(_MathTransformer):
        _FUNCS = {**_MathTransformer._FUNCS, "twice": scalar}
        _VECTOR_IMPL = {**_MathTransformer._VECTOR_IMPL, "twice": (lambda x: x, lambda x: x)}

    class _OverriddenFrame(TtsDataFrame):
        MATH_TRANSFORMER = _OverriddenTransformer

    frame = _frame(cls=_OverriddenFrame)
    out = _run(frame, "d = twice(a)", 0, True, monkeypatch)

    assert not isinstance(out, Exception)
    assert len(counter) == 6
    assert out[out["label"] == "d"]["value"].tolist() == [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]
