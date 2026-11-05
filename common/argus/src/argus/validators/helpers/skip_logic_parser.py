from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

import polars as pl

"""
This is used to convert kobo skip logic into a polars expression.

Not all possible functions are currently supported. Any unsupported
functions will raise an error.

"""

# AST node types

CmpOp = Literal["=", "!=", "<", ">", "<=", ">="]
ArithOp = Literal["+", "-", "*", "div", "mod"]
COMPARISON_OPS: frozenset[str] = frozenset({"=", "!=", "<", ">", "<=", ">="})
MULT_OPS: dict[str, ArithOp] = {"*": "*", "div": "div", "mod": "mod"}
ADD_OPS: dict[str, ArithOp] = {"+": "+", "-": "-"}
CMP_OPS: dict[str, CmpOp] = {"=": "=", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">="}


@dataclass(frozen=True, slots=True)
class Ref:
    name: str


@dataclass(frozen=True, slots=True)
class Lit:
    value: str


@dataclass(frozen=True, slots=True)
class Num:
    value: str


@dataclass(frozen=True, slots=True)
class Bool:
    value: bool


@dataclass(frozen=True, slots=True)
class Or:
    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class And:
    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class Not:
    operand: Expr


@dataclass(frozen=True, slots=True)
class Cmp:
    op: CmpOp
    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class Arith:
    op: ArithOp
    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class Neg:
    operand: Expr


@dataclass(frozen=True, slots=True)
class Selected:
    var: str
    value: str


@dataclass(frozen=True, slots=True)
class CountSelected:
    var: str


@dataclass(frozen=True, slots=True)
class StartsWith:
    var: str
    prefix: str


@dataclass(frozen=True, slots=True)
class EndsWith:
    var: str
    suffix: str


@dataclass(frozen=True, slots=True)
class Contains:
    var: str
    value: str


@dataclass(frozen=True, slots=True)
class Regex:
    var: str
    pattern: str


@dataclass(frozen=True, slots=True)
class StringLength:
    var: str


@dataclass(frozen=True, slots=True)
class Coalesce:
    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class Concat:
    args: list[Expr]


@dataclass(frozen=True, slots=True)
class If:
    cond: Expr
    then: Expr
    otherwise: Expr


@dataclass(frozen=True, slots=True)
class NumCast:
    fn: Literal["int", "number"]
    arg: Expr


@dataclass(frozen=True, slots=True)
class Sum:
    vars: list[str] = field(default_factory=list)


Token = tuple[str, str]

Expr = (
    Ref
    | Lit
    | Num
    | Bool
    | Or
    | And
    | Not
    | Cmp
    | Arith
    | Neg
    | Selected
    | CountSelected
    | StartsWith
    | EndsWith
    | Contains
    | Regex
    | StringLength
    | Coalesce
    | Concat
    | If
    | NumCast
    | Sum
)

# Tokenizer

TOKEN_RE = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<ref>\$\{[^}]+\})
    | (?P<string>'[^']*'|"[^"]*")
    | (?P<number>\d+\.\d+|\d+)
    | (?P<op>>=|<=|!=|=|>|<|\+|-|\*|\(|\)|,)
    | (?P<name>[A-Za-z_][A-Za-z0-9_.\-]*)
    """,
    re.VERBOSE,
)

REF_RE = re.compile(r"\$\{([^}]+)\}")


def get_all_references(expressions: list[str]) -> set[str]:
    """Extracts all referenced columns from a list of skip logic expressions."""
    references = set[str]().union(
        *(
            {str(m).strip().lower() for m in REF_RE.findall(expression)}
            for expression in expressions
        )
    )
    return references


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise ValueError(f"Skip logic parser: Cannot tokenize near: {text[pos : pos + 20]!r}")
        pos = m.end()
        kind = m.lastgroup
        value = m.group()
        if kind == "ws":
            continue
        if kind == "ref":
            tokens.append(("REF", value[2:-1].strip().lower()))  # strip ${ }
        elif kind == "string":
            tokens.append(("STR", value[1:-1]))
        elif kind == "number":
            tokens.append(("NUM", value))
        elif kind == "op":
            tokens.append(("OP", value))
        else:
            tokens.append(("NAME", value))  # and/or/not/div/mod/selected...
    return tokens


# Recursive-descent parser (produces dataclass AST nodes)
# Precedence (loosest -> tightest):  or, and, not, comparison, +- , */div/mod


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens: list[Token] = tokens
        self.i: int = 0

    def peek(self) -> Token | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def advance(self) -> Token:
        tok = self.peek()
        if tok is None:
            raise ValueError("Skip logic parser: Unexpected end of expression")
        self.i += 1
        return tok

    def expect_op(self, symbol: str) -> None:
        tok = self.advance()
        if tok != ("OP", symbol):
            raise ValueError(f"Skip logic parser: Expected {symbol!r}, got {tok}")

    def parse(self) -> Expr:
        node = self.parse_or()
        if self.peek() is not None:
            raise ValueError(f"Skip logic parser: Trailing tokens: {self.tokens[self.i :]}")
        return node

    def parse_or(self) -> Expr:
        node = self.parse_and()
        while self.peek() == ("NAME", "or"):
            _ = self.advance()
            node = Or(node, self.parse_and())
        return node

    def parse_and(self) -> Expr:
        node = self.parse_not()
        while self.peek() == ("NAME", "and"):
            _ = self.advance()
            node = And(node, self.parse_not())
        return node

    def parse_not(self) -> Expr:
        if self.peek() == ("NAME", "not"):
            _ = self.advance()
            return Not(self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self) -> Expr:
        node = self.parse_additive()
        tok = self.peek()
        if tok is not None and tok[0] == "OP" and tok[1] in COMPARISON_OPS:
            op = CMP_OPS[self.advance()[1]]
            return Cmp(op, node, self.parse_additive())
        return node

    def parse_additive(self) -> Expr:
        node = self.parse_multiplicative()
        while self.peek() in (("OP", "+"), ("OP", "-")):
            op = ADD_OPS[self.advance()[1]]
            node = Arith(op, node, self.parse_multiplicative())
        return node

    def parse_multiplicative(self) -> Expr:
        node = self.parse_atom()
        while True:
            tok = self.peek()
            if tok in (("OP", "*"), ("NAME", "div"), ("NAME", "mod")):
                op = MULT_OPS[self.advance()[1]]
                node = Arith(op, node, self.parse_atom())
            else:
                return node

    def parse_atom(self) -> Expr:
        tok = self.advance()
        kind, value = tok

        if kind == "REF":
            return Ref(value)
        if kind == "STR":
            return Lit(value)
        if kind == "NUM":
            return Num(value)
        if kind == "OP" and value == "(":
            node = self.parse_or()
            self.expect_op(")")
            return node
        if kind == "OP" and value == "-":
            node = self.parse_atom()
            if isinstance(node, Num):
                # -(-5) = 5: absorb instead of producing the unparsable '--5'
                if node.value.startswith("-"):
                    return Num(node.value[1:])
                return Num("-" + node.value)
            return Neg(node)
        if kind == "NAME":
            return self._parse_name(value)

        raise ValueError(f"Skip logic parser: Unexpected token: {tok}")

    def _parse_name(self, value: str) -> Expr:
        if self.peek() != ("OP", "("):
            if value in ("true", "false"):
                return Bool(value == "true")
            raise ValueError(f"Skip logic parser: Unexpected token: ('NAME', {value!r})")

        _ = self.advance()  # consume '('

        if self.peek() == ("OP", ")"):
            # Zero-argument function: true(), false(), ...
            _ = self.advance()
            if value in ("true", "false"):
                return Bool(value == "true")
            raise ValueError(
                f"Skip logic parser: Unsupported function: {value}()."
                + " Raise an issue to have it added."
            )

        # At least one argument
        args = [self.parse_or()]
        while self.peek() == ("OP", ","):
            _ = self.advance()
            args.append(self.parse_or())
        self.expect_op(")")

        return self._dispatch_function(value, args)

    @staticmethod
    def _dispatch_function(name: str, args: list[Expr]) -> Expr:

        if name == "selected":
            if len(args) != 2 or not isinstance(args[0], Ref):
                raise ValueError("Skip logic parser: selected() expects (${var}, 'value')")
            if not isinstance(args[1], Lit):
                raise ValueError("Skip logic parser: selected() value must be a quoted string")
            return Selected(args[0].name, args[1].value)

        if name == "starts-with":
            if len(args) != 2 or not isinstance(args[0], Ref):
                raise ValueError("Skip logic parser: starts-with() expects (${var}, 'prefix')")
            if not isinstance(args[1], Lit):
                raise ValueError("Skip logic parser: starts-with() value must be a quoted string")
            return StartsWith(args[0].name, args[1].value)

        if name == "ends-with":
            if len(args) != 2 or not isinstance(args[0], Ref):
                raise ValueError("Skip logic parser: ends-with() expects (${var}, 'suffix')")
            if not isinstance(args[1], Lit):
                raise ValueError("Skip logic parser: ends-with() value must be a quoted string")
            return EndsWith(args[0].name, args[1].value)

        if name == "contains":
            if len(args) != 2 or not isinstance(args[0], Ref):
                raise ValueError("Skip logic parser: contains() expects (${var}, 'substring')")
            if not isinstance(args[1], Lit):
                raise ValueError("Skip logic parser: contains() value must be a quoted string")
            return Contains(args[0].name, args[1].value)

        if name == "regex":
            if len(args) != 2 or not isinstance(args[0], Ref):
                raise ValueError("Skip logic parser: regex() expects (${var}, 'pattern')")
            if not isinstance(args[1], Lit):
                raise ValueError("Skip logic parser: regex() pattern must be a quoted string")
            return Regex(args[0].name, args[1].value)

        if name == "string-length":
            if len(args) != 1 or not isinstance(args[0], Ref):
                raise ValueError("Skip logic parser: string-length() expects (${var},)")
            return StringLength(args[0].name)

        if name == "coalesce":
            if len(args) != 2:
                raise ValueError("Skip logic parser: coalesce() expects exactly 2 arguments")
            return Coalesce(args[0], args[1])

        if name == "concat":
            if not args:
                raise ValueError("Skip logic parser: concat() requires at least one argument")
            return Concat(args)

        if name == "if":
            if len(args) != 3:
                raise ValueError("Skip logic parser: if() expects (condition, then, else)")
            return If(args[0], args[1], args[2])

        if name in ("int", "number"):
            if len(args) != 1:
                raise ValueError(f"Skip logic parser: {name}() takes exactly one argument")
            return NumCast(name, args[0])  # type: ignore[arg-type]

        if name == "count-selected":
            if len(args) != 1 or not isinstance(args[0], Ref):
                raise ValueError("Skip logic parser: count-selected() expects (${var},)")
            return CountSelected(args[0].name)

        if name == "sum":
            if not args:
                raise ValueError("Skip logic parser: sum() requires at least one argument")
            if not all(isinstance(a, Ref) for a in args):
                raise ValueError("Skip logic parser: sum() expects column references")
            return Sum([a.name for a in args])

        if name in ("true", "false"):
            raise ValueError(f"Skip logic parser: {name}() takes no arguments")

        raise ValueError(f"Skip logic parser: Unsupported function: {name}()")


# AST -> Polars expression


# This map only holds type-safe lambdas; whether to cast is decided below.
def _cmp(left: pl.Expr, right: pl.Expr, op: CmpOp) -> pl.Expr:
    if op == "=":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return left < right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    return left >= right


def _arith(left: pl.Expr, right: pl.Expr, op: ArithOp) -> pl.Expr:
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "div":
        return left / right
    return left % right


def _to_expr(node: Expr, schema: dict[str, pl.DataType]) -> pl.Expr:
    def _is_numeric_node(n: Expr) -> bool:
        """True if the node evaluates to a number by construction."""
        if isinstance(n, (Num, Arith, CountSelected, Sum)):
            return True
        if isinstance(n, Neg):
            return _is_numeric_node(n.operand)
        return isinstance(n, StringLength)

    if isinstance(node, Lit):
        return pl.lit(node.value)
    if isinstance(node, Num):
        return pl.lit(float(node.value))
    if isinstance(node, Bool):
        return pl.lit(node.value)
    if isinstance(node, Ref):
        col = pl.col(node.name)
        dtype = schema[node.name]
        if isinstance(dtype, (pl.String, pl.Utf8)):
            return col.str.strip_chars().replace("", None)
        return col

    if isinstance(node, Or):
        return _to_expr(node.left, schema) | _to_expr(node.right, schema)
    if isinstance(node, And):
        return _to_expr(node.left, schema) & _to_expr(node.right, schema)
    if isinstance(node, Not):
        return ~_to_expr(node.operand, schema)

    if isinstance(node, Neg):
        return -_to_expr(node.operand, schema).cast(pl.Float64, strict=False)

    if isinstance(node, Cmp):
        left_side, right_side = (
            _to_expr(node.left, schema),
            _to_expr(node.right, schema),
        )

        # Force numeric cast if either side contains arithmetic operations.
        # +, -, *, div, mod are only defined for numbers.
        if _is_numeric_node(node.left) or _is_numeric_node(node.right):
            # literal numbers or count-selected()
            # rounding for cases when 1 changes to 1.0
            left_side = left_side.cast(pl.Float64, strict=False).round(3)
            right_side = right_side.cast(pl.Float64, strict=False).round(3)

        elif isinstance(node.left, Lit) or isinstance(node.right, Lit):
            left_side = left_side.cast(pl.String, strict=False)
            right_side = right_side.cast(pl.String, strict=False)

        return _cmp(left_side, right_side, node.op).fill_null(False)

    if isinstance(node, Arith):
        left_side, right_side = (
            _to_expr(node.left, schema),
            _to_expr(node.right, schema),
        )
        left_side = left_side.cast(pl.Float64, strict=False)
        right_side = right_side.cast(pl.Float64, strict=False)
        return _arith(left_side, right_side, node.op)

    if isinstance(node, Selected):
        # Multi-select answers are stored as space-separated option codes,
        # e.g. "yes water food". This also works for select_one columns.
        return (
            pl.col(node.var)
            .cast(pl.String)
            .str.strip_chars()
            .str.to_lowercase()
            .str.split(" ")
            .list.contains(node.value.lower())
            .fill_null(False)
        )

    if isinstance(node, StartsWith):
        # Prefix match on the first word of the (possibly space-separated)
        # answer. Lowercased for consistency with selected().
        return (
            pl.col(node.var)
            .cast(pl.String, strict=False)
            .str.strip_chars()
            .str.to_lowercase()
            .str.starts_with(node.prefix.lower())
            .fill_null(False)
        )

    if isinstance(node, EndsWith):
        return (
            pl.col(node.var)
            .cast(pl.String, strict=False)
            .str.strip_chars()
            .str.to_lowercase()
            .str.ends_with(node.suffix.lower())
            .fill_null(False)
        )

    if isinstance(node, Contains):
        # literal=True: the argument is a plain substring, never a regex,
        # so characters like '(' or '*' match literally (ODK behaviour).
        return (
            pl.col(node.var)
            .cast(pl.String, strict=False)
            .str.strip_chars()
            .str.to_lowercase()
            .str.contains(pl.lit(node.value.lower()), literal=True)
            .fill_null(False)
        )

    if isinstance(node, Regex):
        return (
            pl.col(node.var)
            .cast(pl.String, strict=False)
            .str.strip_chars()
            .str.contains(node.pattern)
            .fill_null(False)
        )

    if isinstance(node, StringLength):
        # string-length of an unanswered question is 0 (ODK returns the
        # length of ''; a null-propagating len() would poison arithmetic)
        return (
            pl.when(pl.col(node.var).is_null())
            .then(pl.lit(0))
            .otherwise(
                pl.col(node.var).cast(pl.String, strict=False).str.strip_chars().str.len_chars()
            )
            .cast(pl.Float64)
        )

    if isinstance(node, Coalesce):
        left_side = _to_expr(node.left, schema)
        right_side = _to_expr(node.right, schema)
        return pl.coalesce(left_side, right_side)

    if isinstance(node, Concat):
        parts = [_to_expr(a, schema).cast(pl.String, strict=False).fill_null("") for a in node.args]
        out = parts[0]
        for part in parts[1:]:
            out = out + part
        return out

    if isinstance(node, If):
        return (
            pl.when(_to_expr(node.cond, schema).fill_null(False))
            .then(_to_expr(node.then, schema))
            .otherwise(_to_expr(node.otherwise, schema))
        )

    if isinstance(node, NumCast):
        dtype = pl.Int64 if node.fn == "int" else pl.Float64
        return _to_expr(node.arg, schema).cast(dtype, strict=False)

    if isinstance(node, CountSelected):
        # Number of selected options. An unanswered (null/empty) question
        # must yield 0 — a raw split on null would give a null length
        # and poison the surrounding arithmetic.
        return (
            pl.when(pl.col(node.var).is_null())
            .then(pl.lit(0))
            .otherwise(
                pl.col(node.var)
                .cast(pl.String, strict=False)
                .str.strip_chars()
                .replace("", None)
                .str.split(" ")
                .list.len()
            )
            .fill_null(0)
        )

    if isinstance(node, Sum):
        # Row-wise sum across the referenced columns. Unanswered refs
        # contribute 0 (ODK: sum over an empty nodeset is 0), and a null
        # part must never poison the result with a null sum.
        parts = [
            (
                pl.when(pl.col(v).is_null())
                .then(pl.lit(0.0))
                .otherwise(
                    pl.col(v).cast(pl.String, strict=False).str.strip_chars().replace("", None)
                )
                .cast(pl.Float64, strict=False)
                .fill_null(0.0)
            )
            for v in node.vars
        ]
        out = parts[0]
        for part in parts[1:]:
            out = out + part
        return out


def _iter_refs(node: Expr) -> Iterator[str]:
    if isinstance(
        node, (Ref, Selected, CountSelected, StartsWith, EndsWith, Contains, Regex, StringLength)
    ):
        yield node.name if isinstance(node, Ref) else node.var
    elif isinstance(node, Sum):
        yield from node.vars
    elif isinstance(node, (Or, And, Cmp, Arith, Coalesce)):
        yield from _iter_refs(node.left)
        yield from _iter_refs(node.right)
    elif isinstance(node, (Not, Neg)):
        yield from _iter_refs(node.operand)
    elif isinstance(node, NumCast):
        yield from _iter_refs(node.arg)
    elif isinstance(node, Concat):
        for arg in node.args:
            yield from _iter_refs(arg)
    elif isinstance(node, If):
        yield from _iter_refs(node.cond)
        yield from _iter_refs(node.then)
        yield from _iter_refs(node.otherwise)


def build_relevance_expression(relevant: str, schema: dict[str, pl.DataType]) -> pl.Expr:
    """Parse a Kobo 'relevant' string into a single non-null Boolean Polars expr."""
    ast = Parser(tokenize(str(relevant))).parse()
    for ref in _iter_refs(ast):
        if ref not in schema:
            raise ValueError(
                f"Skip logic parser: Referenced column {ref!r} not found in data."
                + " Note: cross dataset references are currently not supported."
            )

    return _to_expr(ast, schema).fill_null(False)


# Validator: compare skip logic against the collected data


def is_missing(col: str) -> pl.Expr:
    # null, empty string, or whitespace-only
    return (
        pl.col(col)
        .cast(pl.String, strict=False)
        .str.strip_chars()
        .eq("")
        .fill_null(True)  # null -> True (missing)
    )
