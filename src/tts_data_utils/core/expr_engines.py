import lark
import numpy as np
import re


class _FilterExprError(Exception):
    pass


class _FilterTransformer(lark.Transformer):

    def __init__(self, df):
        super().__init__()
        self._df = df

    @lark.v_args(inline=True)
    def int_val(self, tok):
        # Allow Python-style underscores in integer literals
        return int(str(tok).replace("_", ""))

    @lark.v_args(inline=True)
    def float_val(self, tok):
        # Allow Python-style underscores in float literals
        return float(str(tok).replace("_", ""))

    @lark.v_args(inline=True)
    def string_val(self, tok):
        return str(tok)[1:-1]

    @lark.v_args(inline=True)
    def true_val(self, _tok):
        return True

    @lark.v_args(inline=True)
    def false_val(self, _tok):
        return False

    @lark.v_args(inline=True)
    def null_val(self, _tok):
        return None

    @lark.v_args(inline=True)
    def column(self, tok):
        name = str(tok)
        if name not in self._df.columns:
            raise _FilterExprError(
                f"Column {name!r} not found; available: {list(self._df.columns)}")
        return self._df[name]

    @lark.v_args(inline=True)
    def gt(self, left, right):
        return left > right

    @lark.v_args(inline=True)
    def ge(self, left, right):
        return left >= right

    @lark.v_args(inline=True)
    def lt(self, left, right):
        return left < right

    @lark.v_args(inline=True)
    def le(self, left, right):
        return left <= right

    @lark.v_args(inline=True)
    def eq(self, left, right):
        # Treat comparisons to None like null checks, consistent with ``is``.
        if right is None:
            return left.isna() if hasattr(left, 'isna') else (left is None)
        return left == right

    @lark.v_args(inline=True)
    def ne(self, left, right):
        # Treat comparisons to None like null checks, consistent with ``is not``.
        if right is None:
            return left.notna() if hasattr(left, 'notna') else (left is not None)
        return left != right

    @lark.v_args(inline=True)
    def is_(self, left, right):
        if right is None:
            return left.isna() if hasattr(left, 'isna') else (left is None)
        return left == right

    @lark.v_args(inline=True)
    def is_not(self, left, right):
        if right is None:
            return left.notna() if hasattr(left, 'notna') else (left is not None)
        return left != right

    @lark.v_args(inline=True)
    def and_(self, *children):
        # Accept either (left, right) or (left, AND_KW, right)
        if len(children) == 2:
            left, right = children
        elif len(children) == 3:
            left, _op, right = children
        else:  # pragma: no cover - defensive
            raise TypeError(f"_FilterTransformer.and_ expected 2 or 3 args, got {len(children)}")
        return left & right

    @lark.v_args(inline=True)
    def or_(self, *children):
        # Accept either (left, right) or (left, OR_KW, right)
        if len(children) == 2:
            left, right = children
        elif len(children) == 3:
            left, _op, right = children
        else:  # pragma: no cover - defensive
            raise TypeError(f"_FilterTransformer.or_ expected 2 or 3 args, got {len(children)}")
        return left | right

    @lark.v_args(inline=True)
    def not_(self, *children):
        # Accept either (operand,) or (NOT_KW, operand)
        if len(children) == 1:
            (operand,) = children
        elif len(children) == 2:
            _op, operand = children
        else:  # pragma: no cover - defensive
            raise TypeError(f"_FilterTransformer.not_ expected 1 or 2 args, got {len(children)}")
        return ~operand

    @lark.v_args(inline=True)
    def list(self, *items):
        return list(items)

    @lark.v_args(inline=True)
    def in_(self, *children):
        # Accept (left, right) or (left, IN_KW, right)
        if len(children) == 2:
            left, right = children
        elif len(children) == 3:
            left, _op, right = children
        else:  # pragma: no cover - defensive
            raise TypeError(f"_FilterTransformer.in_ expected 2 or 3 args, got {len(children)}")
        if hasattr(left, "isin"):
            return left.isin(right)
        return left in right

    @lark.v_args(inline=True)
    def not_in(self, *children):
        # Accept (left, right) or (left, NOT_KW, IN_KW, right)
        if len(children) == 2:
            left, right = children
        elif len(children) == 3:
            left, _op, right = children
        elif len(children) == 4:
            left, _not_kw, _in_kw, right = children
        else:  # pragma: no cover - defensive
            raise TypeError(f"_FilterTransformer.not_in expected 2-4 args, got {len(children)}")
        if hasattr(left, "isin"):
            return ~left.isin(right)
        return left not in right


class _ParsedFilter:

    def __init__(self, tree):
        self._tree = tree
        self.labels = list(dict.fromkeys(
            str(subtree.children[0])
            for subtree in tree.iter_subtrees()
            if subtree.data == 'column'
        ))

    def eval(self, df):
        try:
            return _FilterTransformer(df).transform(self._tree)
        except lark.exceptions.VisitError as e:
            raise e.orig_exc


class _FilterEngine:

    _parser = lark.Lark(r"""
        %import unicode.WS
        %ignore WS

        AND_KW: "and"
        OR_KW:  "or"
        NOT_KW: "not"
        IN_KW:  "in"

        // Numeric literals: allow underscores like Python (e.g. 3_600_000)
        SIGNED_FLOAT: /[+-]?(?:\d(?:_?\d)*\.\d(?:_?\d)*(?:[eE][+-]?\d(?:_?\d)*)?|\d(?:_?\d)*[eE][+-]?\d(?:_?\d)*)/
        SIGNED_INT:   /[+-]?\d(?:_?\d)*/

        %import common.CNAME -> NAME

        STRING:     "\"" /[^\"]*/ "\"" | "'" /[^']*/ "'"
        NULL_KW:    "None" | "null" | "none"
        BOOL_TRUE:  "True" | "true"
        BOOL_FALSE: "False" | "false"

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

    def parse(self, expr: str) -> _ParsedFilter:
        try:
            tree = self._parser.parse(expr)
        except lark.UnexpectedInput as e:
            raise _FilterExprError(f"Invalid filter expression: {expr!r}") from e
        return _ParsedFilter(tree)


_filter_engine = _FilterEngine()


class _MathExprError(Exception):
    pass


class _MathTransformer(lark.Transformer):

    _FUNCS = {
        'abs': abs, 'sqrt': np.sqrt, 'sin': np.sin, 'cos': np.cos,
        'tan': np.tan, 'log': np.log, 'log10': np.log10, 'exp': np.exp,
        'floor': np.floor, 'ceil': np.ceil,
    }

    def __init__(self, values):
        super().__init__()
        self._values = values

    @lark.v_args(inline=True)
    def int_val(self, tok):
        # Allow Python-style underscores in integer literals
        return int(str(tok).replace("_", ""))

    @lark.v_args(inline=True)
    def float_val(self, tok):
        # Allow Python-style underscores in float literals
        return float(str(tok).replace("_", ""))

    @lark.v_args(inline=True)
    def string_val(self, tok):
        # Strip surrounding quotes from the STRING token
        return str(tok)[1:-1]

    @lark.v_args(inline=True)
    def column(self, tok):
        name = str(tok)
        if name not in self._values:
            raise _MathExprError(f"Label {name!r} not available")
        return self._values[name]

    @lark.v_args(inline=True)
    def func_call(self, name_tok, *args):
        fname = str(name_tok)
        func = self._FUNCS.get(fname)
        if func is None:
            raise _MathExprError(f"Unknown function {fname!r}")
        try:
            return func(*args)
        except Exception as e:  # pragma: no cover - defensive
            raise _MathExprError(f"Error in function {fname!r}: {e}") from e

    @lark.v_args(inline=True)
    def add(self, l, r): return l + r

    @lark.v_args(inline=True)
    def sub(self, l, r): return l - r

    @lark.v_args(inline=True)
    def mul(self, l, r): return l * r

    @lark.v_args(inline=True)
    def div(self, l, r): return l / r

    @lark.v_args(inline=True)
    def floordiv(self, l, r): return l // r

    @lark.v_args(inline=True)
    def neg(self, val): return -val

    @lark.v_args(inline=True)
    def pow_(self, base, exp): return base ** exp

    # Comparison operators

    @lark.v_args(inline=True)
    def gt(self, l, r): return l > r

    @lark.v_args(inline=True)
    def ge(self, l, r): return l >= r

    @lark.v_args(inline=True)
    def lt(self, l, r): return l < r

    @lark.v_args(inline=True)
    def le(self, l, r): return l <= r

    @lark.v_args(inline=True)
    def eq(self, l, r): return l == r

    @lark.v_args(inline=True)
    def ne(self, l, r): return l != r

    @lark.v_args(inline=True)
    def list(self, *items):
        return list(items)

    @lark.v_args(inline=True)
    def in_(self, *children):
        # Accept (left, right) or (left, IN_KW, right)
        if len(children) == 2:
            l, r = children
        elif len(children) == 3:
            l, _op, r = children
        else:  # pragma: no cover - defensive
            raise TypeError(f"_MathTransformer.in_ expected 2 or 3 args, got {len(children)}")
        return l in r

    # Boolean combinators (operate on scalar booleans)

    @lark.v_args(inline=True)
    def and_(self, *children):
        # Accept (left, right) or (left, AND_KW, right)
        if len(children) == 2:
            l, r = children
        elif len(children) == 3:
            l, _op, r = children
        else:  # pragma: no cover - defensive
            raise TypeError(f"_MathTransformer.and_ expected 2 or 3 args, got {len(children)}")
        return l and r

    @lark.v_args(inline=True)
    def or_(self, *children):
        # Accept (left, right) or (left, OR_KW, right)
        if len(children) == 2:
            l, r = children
        elif len(children) == 3:
            l, _op, r = children
        else:  # pragma: no cover - defensive
            raise TypeError(f"_MathTransformer.or_ expected 2 or 3 args, got {len(children)}")
        return l or r

    @lark.v_args(inline=True)
    def not_(self, *children):
        # Accept (operand,) or (NOT_KW, operand)
        if len(children) == 1:
            (v,) = children
        elif len(children) == 2:
            _op, v = children
        else:  # pragma: no cover - defensive
            raise TypeError(f"_MathTransformer.not_ expected 1 or 2 args, got {len(children)}")
        return not v


class _ParsedMath:

    def __init__(self, tree, transformer_cls):
        self._tree = tree
        self._transformer_cls = transformer_cls
        self.labels = list(dict.fromkeys(
            str(subtree.children[0])
            for subtree in tree.iter_subtrees()
            if subtree.data == 'column'
        ))

    def eval(self, values):
        try:
            return self._transformer_cls(values).transform(self._tree)
        except lark.exceptions.VisitError as e:
            raise e.orig_exc


class _MathEngine:

    _parser = lark.Lark(r"""
        %import unicode.WS
        %ignore WS

        AND_KW: "and"
        OR_KW:  "or"
        NOT_KW: "not"
        IN_KW:  "in"

        // Numeric literals: allow underscores like Python (e.g. 3_600_000)
        SIGNED_FLOAT: /[+-]?(?:\d(?:_?\d)*\.\d(?:_?\d)*(?:[eE][+-]?\d(?:_?\d)*)?|\d(?:_?\d)*[eE][+-]?\d(?:_?\d)*)/
        SIGNED_INT:   /[+-]?\d(?:_?\d)*/

        %import common.CNAME -> NAME

        STRING:     "\"" /[^\"]*/ "\"" | "'" /[^']*/ "'"

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
            | mul_expr "//" unary_expr -> floordiv
            | mul_expr "/" unary_expr  -> div

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

    def parse(self, expr: str, transformer_cls=_MathTransformer) -> _ParsedMath:
        """Parse an expression into a tree bound to the given transformer.

        Parameters
        ----------
        expr : str
            The expression to parse.
        transformer_cls : type
            A subclass of :class:`_MathTransformer` that will be used to
            evaluate the expression tree. Defaults to the core
            :class:`_MathTransformer`.
        """
        # Normalise numeric literals that use a leading dot (e.g. .5, .0000005)
        # into a form accepted by the grammar (0.5, 0.0000005). The grammar
        # requires a digit before the decimal point, but many of the
        # dictionary-sourced expressions use the shorthand .x. Since this
        # language has no attribute access syntax (x.y), a bare leading
        # dot followed by digits is always a numeric literal.
        normalised_expr = re.sub(r"(?<!\d)\.(\d)", r"0.\1", expr)

        try:
            tree = self._parser.parse(normalised_expr)
        except lark.UnexpectedInput as e:
            # Report the original expression in the error message so that
            # callers/logs see exactly what was provided.
            raise _MathExprError(f"Invalid math expression: {expr!r}") from e
        return _ParsedMath(tree, transformer_cls)


_math_engine = _MathEngine()
