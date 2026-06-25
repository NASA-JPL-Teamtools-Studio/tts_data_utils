import lark
import numpy as np


class _FilterExprError(Exception):
    pass


class _FilterTransformer(lark.Transformer):

    def __init__(self, df):
        super().__init__()
        self._df = df

    @lark.v_args(inline=True)
    def int_val(self, tok):
        return int(tok)

    @lark.v_args(inline=True)
    def float_val(self, tok):
        return float(tok)

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
        return left == right

    @lark.v_args(inline=True)
    def ne(self, left, right):
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
    def and_(self, left, right):
        return left & right

    @lark.v_args(inline=True)
    def or_(self, left, right):
        return left | right

    @lark.v_args(inline=True)
    def not_(self, operand):
        return ~operand


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
    def int_val(self, tok): return int(tok)

    @lark.v_args(inline=True)
    def float_val(self, tok): return float(tok)

    @lark.v_args(inline=True)
    def column(self, tok):
        name = str(tok)
        if name not in self._values:
            raise _MathExprError(f"Label {name!r} not available")
        return self._values[name]

    @lark.v_args(inline=True)
    def func_call(self, name_tok, val):
        fname = str(name_tok)
        if fname not in self._FUNCS:
            raise _MathExprError(f"Unknown function {fname!r}")
        return self._FUNCS[fname](val)

    @lark.v_args(inline=True)
    def add(self, l, r): return l + r

    @lark.v_args(inline=True)
    def sub(self, l, r): return l - r

    @lark.v_args(inline=True)
    def mul(self, l, r): return l * r

    @lark.v_args(inline=True)
    def div(self, l, r): return l / r

    @lark.v_args(inline=True)
    def neg(self, val): return -val

    @lark.v_args(inline=True)
    def pow_(self, base, exp): return base ** exp


class _ParsedMath:

    def __init__(self, tree):
        self._tree = tree
        self.labels = list(dict.fromkeys(
            str(subtree.children[0])
            for subtree in tree.iter_subtrees()
            if subtree.data == 'column'
        ))

    def eval(self, values):
        try:
            return _MathTransformer(values).transform(self._tree)
        except lark.exceptions.VisitError as e:
            raise e.orig_exc


class _MathEngine:

    _parser = lark.Lark(r"""
        %import unicode.WS
        %ignore WS

        %import common (SIGNED_INT, SIGNED_FLOAT)
        %import common.CNAME -> NAME

        ?start: expr

        ?expr: add_expr

        ?add_expr: mul_expr
            | add_expr "+" mul_expr  -> add
            | add_expr "-" mul_expr  -> sub

        ?mul_expr: unary_expr
            | mul_expr "*" unary_expr -> mul
            | mul_expr "/" unary_expr -> div

        ?unary_expr: power_expr
            | "-" unary_expr         -> neg

        ?power_expr: atom
            | atom "**" unary_expr   -> pow_

        ?atom: SIGNED_INT              -> int_val
            | SIGNED_FLOAT             -> float_val
            | NAME "(" expr ")"        -> func_call
            | NAME                     -> column
            | "(" expr ")"
    """, parser='lalr')

    def parse(self, expr: str) -> _ParsedMath:
        try:
            tree = self._parser.parse(expr)
        except lark.UnexpectedInput as e:
            raise _MathExprError(f"Invalid math expression: {expr!r}") from e
        return _ParsedMath(tree)


_math_engine = _MathEngine()
