# Expression Language Changes for `tts_data_utils`

This document describes the desired changes to the expression language used by:

- `_MathEngine` / `_MathTransformer` (math expressions used by `TtsDataFrame.derive_values`)
- `_FilterEngine` / `_FilterTransformer` (boolean filter expressions used by `TtsDataFrame.filter_expr` and `at_times_where`)

The goals are:

- Use **Python-style keywords** for boolean logic: `and`, `or`, `not`.
- Officially treat these as **keywords**, not functions, and support clean infix chaining.
- Add support for the `in` / `not in` operators with **Python-style list syntax**.
- Provide an introspection helper on `TtsDataFrame` that clearly distinguishes **keywords** from **functions**.

## 1. Changes to `_MathEngine` grammar

File: `src/tts_data_utils/core/expr_engines.py`

Current `_MathEngine` grammar (relevant portion):

```lark
    _parser = lark.Lark(r"""
        %import unicode.WS
        %ignore WS

        %import common (SIGNED_INT, SIGNED_FLOAT)
        %import common.CNAME -> NAME

        STRING:     "\"" /[^\"]*/ "\"" | "'" /[^']*/ "'"

        ?start: expr

        # Lowest precedence: boolean OR
        ?expr: or_expr

        ?or_expr: and_expr
            | or_expr "or" and_expr   -> or_

        ?and_expr: cmp_expr
            | and_expr "and" cmp_expr -> and_

        ?cmp_expr: add_expr
            | add_expr ">"  add_expr  -> gt
            | add_expr ">=" add_expr  -> ge
            | add_expr "<"  add_expr  -> lt
            | add_expr "<=" add_expr  -> le
            | add_expr "==" add_expr  -> eq
            | add_expr "!=" add_expr  -> ne

        ?add_expr: mul_expr
            | add_expr "+" mul_expr   -> add
            | add_expr "-" mul_expr   -> sub

        ?mul_expr: unary_expr
            | mul_expr "*" unary_expr -> mul
            | mul_expr "/" unary_expr -> div

        ?unary_expr: power_expr
            | "-" unary_expr          -> neg
            | "not" unary_expr        -> not_

        ?power_expr: atom
            | atom "**" unary_expr    -> pow_

        ?atom: SIGNED_INT              -> int_val
            | SIGNED_FLOAT             -> float_val
            | STRING                   -> string_val
            | NAME "(" [expr ("," expr)*] ")" -> func_call
            | NAME                     -> column
            | "(" expr ")"
    """, parser='lalr')
```

### New `_MathEngine` grammar

We keep Python-style lowercase keywords, but formalize them as dedicated tokens and add `in` / `not in` with list syntax.

Replace the grammar block above with:

```lark
    _parser = lark.Lark(r"""
        %import unicode.WS
        %ignore WS

        %import common (SIGNED_INT, SIGNED_FLOAT)
        %import common.CNAME -> NAME

        STRING:     "\"" /[^\"]*/ "\"" | "'" /[^']*/ "'"

        AND_KW: "and"
        OR_KW:  "or"
        NOT_KW: "not"
        IN_KW:  "in"

        list: "[" [expr ("," expr)*] "]"

        ?start: expr

        # Lowest precedence: boolean OR
        ?expr: or_expr

        ?or_expr: and_expr
            | or_expr OR_KW and_expr   -> or_

        ?and_expr: cmp_expr
            | and_expr AND_KW cmp_expr -> and_

        ?cmp_expr: add_expr
            | add_expr ">"  add_expr  -> gt
            | add_expr ">=" add_expr  -> ge
            | add_expr "<"  add_expr  -> lt
            | add_expr "<=" add_expr  -> le
            | add_expr "==" add_expr  -> eq
            | add_expr "!=" add_expr  -> ne
            | add_expr IN_KW list      -> in_

        ?add_expr: mul_expr
            | add_expr "+" mul_expr   -> add
            | add_expr "-" mul_expr   -> sub

        ?mul_expr: unary_expr
            | mul_expr "*" unary_expr -> mul
            | mul_expr "/" unary_expr -> div

        ?unary_expr: power_expr
            | "-" unary_expr          -> neg
            | NOT_KW unary_expr        -> not_

        ?power_expr: atom
            | atom "**" unary_expr    -> pow_

        ?atom: SIGNED_INT              -> int_val
            | SIGNED_FLOAT             -> float_val
            | STRING                   -> string_val
            | NAME "(" [expr ("," expr)*] ")" -> func_call
            | NAME                     -> column
            | "(" expr ")"
    """, parser='lalr')
```

Notes:

- Keywords are now explicit: `AND_KW`, `OR_KW`, `NOT_KW`, `IN_KW`.
- `in_` is a new comparison operator that takes a scalar left-hand side and a Python-style list.

### New `_MathTransformer` methods

Add these methods to `_MathTransformer`:

```python
    @lark.v_args(inline=True)
    def list(self, *items):
        return list(items)

    @lark.v_args(inline=True)
    def in_(self, l, r):
        return l in r
```

Place them near the existing comparison and boolean methods (e.g. after `ne`).


## 2. Changes to `_FilterEngine` grammar

Current `_FilterEngine` grammar (relevant portion):

```lark
    _parser = lark.Lark(r"""
        %import unicode.WS
        %ignore WS

        %import common (SIGNED_INT, SIGNED_FLOAT)
        %import common.CNAME -> NAME

        STRING:     "\"" /[^"]*/ "\"" | "'" /[^']*/ "'"
        NULL_KW:    "None" | "null" | "none"
        BOOL_TRUE:  "True" | "true"
        BOOL_FALSE: "False" | "false"

        ?start: expr

        ?expr: or_expr

        ?or_expr: and_expr
            | or_expr "or" and_expr   -> or_

        ?and_expr: not_expr
            | and_expr "and" not_expr -> and_

        ?not_expr: comparison
            | "not" not_expr          -> not_

        ?comparison: atom
            | atom ">"  atom          -> gt
            | atom ">=" atom          -> ge
            | atom "<"  atom          -> lt
            | atom "<=" atom          -> le
            | atom "==" atom          -> eq
            | atom "!=" atom          -> ne
            | atom "is" "not" atom    -> is_not
            | atom "is" atom          -> is_

        ?atom: SIGNED_INT             -> int_val
            | SIGNED_FLOAT            -> float_val
            | STRING                  -> string_val
            | NULL_KW                 -> null_val
            | BOOL_TRUE               -> true_val
            | BOOL_FALSE              -> false_val
            | NAME                    -> column
            | "(" expr ")"
    """, parser='lalr')
```

### New `_FilterEngine` grammar

We keep Python-style lowercase keywords and add `in` / `not in` with list syntax.

Replace the grammar block above with:

```lark
    _parser = lark.Lark(r"""
        %import unicode.WS
        %ignore WS

        %import common (SIGNED_INT, SIGNED_FLOAT)
        %import common.CNAME -> NAME

        STRING:     "\"" /[^"]*/ "\"" | "'" /[^']*/ "'"
        NULL_KW:    "None" | "null" | "none"
        BOOL_TRUE:  "True" | "true"
        BOOL_FALSE: "False" | "false"

        AND_KW: "and"
        OR_KW:  "or"
        NOT_KW: "not"
        IN_KW:  "in"

        list: "[" [atom ("," atom)*] "]"

        ?start: expr

        ?expr: or_expr

        ?or_expr: and_expr
            | or_expr OR_KW and_expr   -> or_

        ?and_expr: not_expr
            | and_expr AND_KW not_expr -> and_

        ?not_expr: comparison
            | NOT_KW not_expr          -> not_

        ?comparison: atom
            | atom ">"  atom          -> gt
            | atom ">=" atom          -> ge
            | atom "<"  atom          -> lt
            | atom "<=" atom          -> le
            | atom "==" atom          -> eq
            | atom "!=" atom          -> ne
            | atom "is" "not" atom    -> is_not
            | atom "is" atom          -> is_
            | atom IN_KW list          -> in_
            | atom NOT_KW IN_KW list   -> not_in

        ?atom: SIGNED_INT             -> int_val
            | SIGNED_FLOAT            -> float_val
            | STRING                  -> string_val
            | NULL_KW                 -> null_val
            | BOOL_TRUE               -> true_val
            | BOOL_FALSE              -> false_val
            | NAME                    -> column
            | "(" expr ")"
    """, parser='lalr')
```

### New `_FilterTransformer` methods

Add these methods to `_FilterTransformer`:

```python
    @lark.v_args(inline=True)
    def list(self, *items):
        return list(items)

    @lark.v_args(inline=True)
    def in_(self, left, right):
        if hasattr(left, "isin"):
            return left.isin(right)
        return left in right

    @lark.v_args(inline=True)
    def not_in(self, left, right):
        if hasattr(left, "isin"):
            return ~left.isin(right)
        return left not in right
```

Place them near the existing comparison / boolean methods.

This enables expressions like:

```python
# Filter expressions
frame.filter_expr("mode in [1, 2, 3]")
frame.filter_expr("mode not in ['A', 'B']")

# at_times_where expressions (labels mapped to values)
frame.at_times_where("sensor_001 in [0, 1] and status == 'ok'")
```


## 3. Introspection helper on `TtsDataFrame`

File: `src/tts_data_utils/core/data_frame.py`

Add a helper method to `TtsDataFrame` that returns a dict describing the expression language: engines, transformer class, function names, and keyword sets.

Suggested implementation:

```python
    def inspect_expr_language(self):
        math_engine = self.MATH_ENGINE
        math_transformer = self.MATH_TRANSFORMER

        funcs = getattr(math_transformer, "_FUNCS", {})
        math_functions = sorted(funcs.keys()) if isinstance(funcs, dict) else []

        filter_engine = _filter_engine

        info = {
            "math_engine": type(math_engine),
            "math_transformer": math_transformer,
            "math_functions": math_functions,
            "math_keywords": {
                "boolean": {"and", "or", "not"},
                "comparison": {">", ">=", "<", "<=", "==", "!=", "in"},
            },
            "filter_engine": type(filter_engine),
            "filter_keywords": {
                "boolean": {"and", "or", "not"},
                "comparison": {">", ">=", "<", "<=", "==", "!=", "is", "is not", "in", "not in"},
                "literals": {"None", "null", "none", "True", "true", "False", "false"},
            },
        }

        return info
```

You can place this method near the other expression-related methods (`filter_expr`, `at_times_where`, `derive_values`). It intentionally hard-codes keyword sets to reflect the grammar; if you change the grammar later, you should update this helper as well.

Example usage from a notebook:

```python
info = df.inspect_expr_language()
info["math_functions"]
info["math_keywords"]
info["filter_keywords"]
```

This will give you a clear distinction between:

- **Functions**: callable names like `abs`, `sqrt`, `log`, etc.
- **Keywords / operators**: `and`, `or`, `not`, `in`, `is`, etc., used in infix form.

## 4. Behavioral summary

After applying these changes:

- `derive_values` expressions support:

  ```python
  gps_lock = mode in [1, 2, 3] and sensor_001 > 0.5
  ```

- `filter_expr` and `at_times_where` support:

  ```python
  df.filter_expr("status in ['ok', 'warn'] and count >= 10")
  df.filter_expr("mode not in [1, 2, 3] or flag is None")
  df.at_times_where("sensor_001 in [0, 1] and sensor_002 < 5")
  ```

All boolean logic uses Python-style keywords (`and`, `or`, `not`), and `in` / `not in` work with Python-style list literals, consistent across math and filter expression engines.
