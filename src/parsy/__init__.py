# End-user documentation is in ../../doc/ and so is for the most part not
# duplicated here in the form of doc strings. Code comments and docstrings
# are mainly for internal use.
from __future__ import annotations

import operator
import enum

import re
from dataclasses import dataclass
from functools import reduce, wraps
from typing import Any, Callable, FrozenSet, Generic, Optional, TypeVar, Union


from .version import __version__  # noqa: F401


# Covariance/contravariance:

# Parser[str] is a subtype of Parser[Union[str, int]]
# Result[str] is a subtype of Result[Union[str, int]]
# So we want covariance for these

OUT = TypeVar("OUT")
OUT1 = TypeVar("OUT1")
OUT2 = TypeVar("OUT2")

T = TypeVar("T")


def noop(val: T) -> T:
    return val


def line_info_at(stream: str, index: int) -> tuple[int, int]:
    if index > len(stream):
        raise ValueError("invalid index")
    line = stream.count("\n", 0, index)
    last_nl = stream.rfind("\n", 0, index)
    col = index - (last_nl + 1)
    return (line, col)


class ParseError(RuntimeError):
    def __init__(self, expected: FrozenSet[str], stream: str, index: int):
        self.expected: FrozenSet[str] = expected
        self.stream: str = stream
        self.index: int = index

    def line_info(self) -> str:
        try:
            return "{}:{}".format(*line_info_at(self.stream, self.index))
        except (TypeError, AttributeError):  # not a str
            return str(self.index)

    def __str__(self) -> str:
        expected_list = sorted(repr(e) for e in self.expected)

        if len(expected_list) == 1:
            return f"expected {expected_list[0]} at {self.line_info()}"
        else:
            return f"expected one of {', '.join(expected_list)} at {self.line_info()}"


@dataclass
class Result(Generic[OUT]):
    status: bool
    index: int
    value: OUT
    furthest: int
    expected: FrozenSet[str]

    @staticmethod
    def success(index: int, value: OUT) -> Result[OUT]:
        return Result(True, index, value, -1, frozenset())

    # We don't handle types of failures yet, and always
    # either:
    # - don't return these values (e.g. choose another parser)
    # - raise an exception.

    # Therefore, I think it is safe here to use `Any` as type to keep type checker happy
    # The same issue crops up in various branches that return parse failure results
    @staticmethod
    def failure(index: int, expected: str) -> Result[Any]:
        return Result(False, -1, None, index, frozenset([expected]))

    # collect the furthest failure from self and other
    def aggregate(self: Result[OUT], other: Optional[Result[Any]]) -> Result[OUT]:
        if not other:
            return self

        if self.furthest > other.furthest:
            return self
        elif self.furthest == other.furthest:
            # if we both have the same failure index, we combine the expected messages.
            return Result(self.status, self.index, self.value, self.furthest, self.expected | other.expected)
        else:
            return Result(self.status, self.index, self.value, other.furthest, other.expected)


class Parser(Generic[OUT]):
    """
    A Parser is an object that wraps a function whose arguments are
    a string to be parsed and the index on which to begin parsing.
    The function should return either Result.success(next_index, value),
    where the next index is where to continue the parse and the value is
    the yielded value, or Result.failure(index, expected), where expected
    is a string indicating what was expected, and the index is the index
    of the failure.
    """

    def __init__(self, wrapped_fn: Callable[[str, int], Result[OUT]]):
        self.wrapped_fn: Callable[[str, int], Result[OUT]] = wrapped_fn

    def __call__(self, stream: str, index: int) -> Result[OUT]:
        return self.wrapped_fn(stream, index)

    def parse(self, stream: str) -> OUT:
        """Parse a string and return the result or raise a ParseError."""
        (result, _) = (self << eof).parse_partial(stream)
        return result

    def parse_partial(self, stream: str) -> tuple[OUT, str]:
        """
        Parse the longest possible prefix of a given string.
        Return a tuple of the result and the rest of the string,
        or raise a ParseError.
        """
        result = self(stream, 0)

        if result.status:
            return (result.value, stream[result.index :])
        else:
            raise ParseError(result.expected, stream, result.furthest)

    def bind(self: Parser[OUT1], bind_fn: Callable[[OUT1], Parser[OUT2]]) -> Parser[OUT2]:
        @Parser
        def bound_parser(stream: str, index: int) -> Result[OUT2]:
            result: Result[OUT1] = self(stream, index)

            if result.status:
                next_parser = bind_fn(result.value)
                return next_parser(stream, result.index).aggregate(result)
            else:
                return result  # type: ignore

        return bound_parser

    def map(self: Parser[OUT1], map_fn: Callable[[OUT1], OUT2]) -> Parser[OUT2]:
        return self.bind(lambda res: success(map_fn(res)))

    def concat(self: Parser[list[str]]) -> Parser[str]:
        return self.map("".join)

    def then(self: Parser, other: Parser[OUT2]) -> Parser[OUT2]:
        return (self & other).map(lambda t: t[1])

    def skip(self: Parser[OUT1], other: Parser) -> Parser[OUT1]:
        return (self & other).map(lambda t: t[0])

    def result(self: Parser, res: OUT2) -> Parser[OUT2]:
        return self >> success(res)

    def many(self: Parser[OUT]) -> Parser[list[OUT]]:
        return self.times(0, float("inf"))

    def times(self: Parser[OUT], min: int, max: int | float | None = None) -> Parser[list[OUT]]:
        the_max: int | float
        if max is None:
            the_max = min
        else:
            the_max = max

        # TODO - must execute at least once
        @Parser
        def times_parser(stream: str, index: int) -> Result[list[OUT]]:
            values: list[OUT] = []
            times = 0
            result = None

            while times < the_max:
                result = self(stream, index).aggregate(result)
                if result.status:
                    values.append(result.value)
                    index = result.index
                    times += 1
                elif times >= min:
                    break
                else:
                    return result  # type: ignore

            return Result.success(index, values).aggregate(result)

        return times_parser

    def at_most(self: Parser[OUT], n: int) -> Parser[list[OUT]]:
        return self.times(0, n)

    def at_least(self: Parser[OUT], n: int) -> Parser[list[OUT]]:
        return (self.times(n) & self.many()).map(lambda t: t[0] + t[1])

    # TODO overloads to distinguish calling with and without default
    def optional(self: Parser[OUT1], default: OUT2 | None = None) -> Parser[OUT1 | OUT2 | None]:
        return self.times(0, 1).map(lambda v: v[0] if v else default)

    def until(
        self: Parser[OUT],
        other: Parser[OUT],
        min: int = 0,
        max: int | float = float("inf"),
        consume_other: bool = False,
    ) -> Parser[list[OUT]]:
        @Parser
        def until_parser(stream: str, index: int) -> Result[list[OUT]]:
            values = []
            times = 0
            while True:

                # try parser first
                res = other(stream, index)
                if res.status and times >= min:
                    if consume_other:
                        # consume other
                        values.append(res.value)
                        index = res.index
                    return Result.success(index, values)

                # exceeded max?
                if times >= max:
                    # return failure, it matched parser more than max times
                    return Result.failure(index, f"at most {max} items")

                # failed, try parser
                result = self(stream, index)
                if result.status:
                    # consume
                    values.append(result.value)
                    index = result.index
                    times += 1
                elif times >= min:
                    # return failure, parser is not followed by other
                    return Result.failure(index, "did not find other parser")
                else:
                    # return failure, it did not match parser at least min times
                    return Result.failure(index, f"at least {min} items; got {times} item(s)")

        return until_parser

    def sep_by(self: Parser[OUT], sep: Parser, *, min: int = 0, max: int | float = float("inf")) -> Parser[list[OUT]]:
        zero_times: Parser[list[OUT]] = success([])
        if max == 0:
            return zero_times
        res = (self.times(1) & (sep >> self).times(min - 1, max - 1)).map(lambda t: t[0] + t[1])
        if min == 0:
            res |= zero_times
        return res

    def desc(self, description: str) -> Parser[OUT]:
        @Parser
        def desc_parser(stream: str, index: int) -> Result[OUT]:
            result = self(stream, index)
            if result.status:
                return result
            else:
                return Result.failure(index, description)

        return desc_parser

    def mark(self):
        @generate
        def marked():
            start = yield line_info
            body = yield self
            end = yield line_info
            return (start, body, end)

        return marked

    def tag(self, name):
        return self.map(lambda v: (name, v))

    def should_fail(self, description):
        @Parser
        def fail_parser(stream, index):
            res = self(stream, index)
            if res.status:
                return Result.failure(index, description)
            return Result.success(index, res)

        return fail_parser

    def __add__(self: Parser[str], other: Parser[str]) -> Parser[str]:
        # TODO it would be nice to get more generic type checks here.
        # I want some way of saying "the input value can be any
        # type that has an ``__add__`` method that returns the same type
        # as the two inputs". This would allow us to use it for both
        # `str` and `list`, which satisfy that.
        return (self & other).map(lambda t: t[0] + t[1])

    def __mul__(self, other):
        if isinstance(other, range):
            return self.times(other.start, other.stop - 1)
        return self.times(other)

    def __or__(self: Parser[OUT1], other: Parser[OUT2]) -> Parser[Union[OUT1, OUT2]]:
        @Parser
        def alt_parser(stream: str, index: int) -> Result[Union[OUT1, OUT2]]:
            result0 = None

            # mypy + pyright complain here e.g.
            #  Expression of type "Result[OUT1@__or__]" cannot be assigned to return type
            #  "Result[OUT1@__or__ | OUT2@__or__]"
            #
            # I think it should be enough to say that Result is covariant in its OUT parameter.
            # However, doing that results in a bunch of new errors on other methods:
            #  "covariant type variable cannot be used in parameter type"

            # I think this is due to worrying about immutability, which isn't a worry for us.
            # So we just force it here for now using type:ignore, to keep the number of error
            # message down.

            # We have the same issue in __and__ below

            result1 = self(stream, index).aggregate(result0)
            if result1.status:
                return result1  # type:ignore

            result2 = other(stream, index).aggregate(result1)
            return result2  # type:ignore

        return alt_parser

    def __and__(self: Parser[OUT1], other: Parser[OUT2]) -> Parser[tuple[OUT1, OUT2]]:
        @Parser
        def seq_parser(stream: str, index: int) -> Result[tuple[OUT1, OUT2]]:
            result0 = None
            result1 = self(stream, index).aggregate(result0)
            if not result1.status:
                return result1  # type: ignore
            result2 = other(stream, result1.index).aggregate(result1)
            if not result2.status:
                return result2  # type: ignore

            return Result.success(result2.index, (result1.value, result2.value)).aggregate(result2)

        return seq_parser

    # haskelley operators, for fun #

    # >>
    def __rshift__(self: Parser, other: Parser[OUT2]) -> Parser[OUT2]:
        return self.then(other)

    # <<
    def __lshift__(self: Parser[OUT1], other: Parser) -> Parser[OUT1]:
        return self.skip(other)


# combinator syntax
def generate(fn):
    @Parser
    @wraps(fn)
    def generated(stream, index):
        # start up the generator
        iterator = fn()

        result = None
        value = None
        try:
            while True:
                next_parser = iterator.send(value)
                result = next_parser(stream, index).aggregate(result)
                if not result.status:
                    return result
                value = result.value
                index = result.index
        except StopIteration as stop:
            returnVal = stop.value
            if isinstance(returnVal, Parser):
                return returnVal(stream, index).aggregate(result)

            return Result.success(index, returnVal).aggregate(result)

    return generated


index = Parser(lambda _, index: Result.success(index, index))
line_info = Parser(lambda stream, index: Result.success(index, line_info_at(stream, index)))


def success(val: OUT) -> Parser[OUT]:
    return Parser(lambda _, index: Result.success(index, val))


def fail(expected: str) -> Parser[None]:
    return Parser(lambda _, index: Result.failure(index, expected))


def string(s: str, transform: Callable[[str], str] = noop) -> Parser[str]:
    slen = len(s)
    transformed_s = transform(s)

    @Parser
    def string_parser(stream, index):
        if transform(stream[index : index + slen]) == transformed_s:
            return Result.success(index + slen, s)
        else:
            return Result.failure(index, s)

    return string_parser


def regex(exp, flags=0, group=0) -> Parser[str]:
    if isinstance(exp, (str, bytes)):
        exp = re.compile(exp, flags)
    if isinstance(group, (str, int)):
        group = (group,)

    @Parser
    def regex_parser(stream, index):
        match = exp.match(stream, index)
        if match:
            return Result.success(match.end(), match.group(*group))
        else:
            return Result.failure(index, exp.pattern)

    return regex_parser


def test_item(func, description):
    @Parser
    def test_item_parser(stream, index):
        if index < len(stream):
            if isinstance(stream, bytes):
                # Subscripting bytes with `[index]` instead of
                # `[index:index + 1]` returns an int
                item = stream[index : index + 1]
            else:
                item = stream[index]
            if func(item):
                return Result.success(index + 1, item)
        return Result.failure(index, description)

    return test_item_parser


def test_char(func, description):
    # Implementation is identical to test_item
    return test_item(func, description)


def match_item(item, description=None):
    if description is None:
        description = str(item)
    return test_item(lambda i: item == i, description)


def string_from(*strings: str, transform: Callable[[str], str] = noop) -> Parser[str]:
    # Sort longest first, so that overlapping options work correctly
    return reduce(operator.or_, [string(s, transform) for s in sorted(strings, key=len, reverse=True)])


def char_from(string):
    if isinstance(string, bytes):
        return test_char(lambda c: c in string, b"[" + string + b"]")
    else:
        return test_char(lambda c: c in string, "[" + string + "]")


def peek(parser):
    @Parser
    def peek_parser(stream, index):
        result = parser(stream, index)
        if result.status:
            return Result.success(index, result.value)
        else:
            return result

    return peek_parser


any_char = test_char(lambda c: True, "any character")

whitespace = regex(r"\s+")

letter = test_char(lambda c: c.isalpha(), "a letter")

digit = test_char(lambda c: c.isdigit(), "a digit")

decimal_digit = char_from("0123456789")


@Parser
def eof(stream: str, index: int) -> Result[None]:
    if index >= len(stream):
        return Result.success(index, None)
    else:
        return Result.failure(index, "EOF")


E = TypeVar("E", bound=enum.Enum)


def from_enum(enum_cls: type[E], transform: Callable = noop) -> Parser[E]:
    items = sorted(
        ((str(enum_item.value), enum_item) for enum_item in enum_cls), key=lambda t: len(t[0]), reverse=True
    )
    return reduce(operator.or_, [string(value, transform=transform).result(enum_item) for value, enum_item in items])


class forward_declaration(Parser):
    """
    An empty parser that can be used as a forward declaration,
    especially for parsers that need to be defined recursively.

    You must use `.become(parser)` before using.
    """

    def __init__(self) -> None:
        pass

    def _raise_error(self, *args, **kwargs):
        raise ValueError("You must use 'become' before attempting to call `parse` or `parse_partial`")

    parse = _raise_error
    parse_partial = _raise_error

    def become(self, other: Parser) -> None:
        self.__dict__ = other.__dict__
        self.__class__ = other.__class__
