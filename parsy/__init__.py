# End-user documentation is in ../../doc/ and so is for the most part not
# duplicated here in the form of doc strings. Code comments and docstrings
# are mainly for internal use.
from __future__ import annotations

import enum
import operator
import re
from dataclasses import Field, dataclass, field, fields
from functools import reduce, wraps
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    FrozenSet,
    Generator,
    Generic,
    List,
    Literal,
    Mapping,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from typing_extensions import ParamSpec, Protocol, TypeVarTuple, Unpack

OUT = TypeVar("OUT")
OUT1 = TypeVar("OUT1")
OUT2 = TypeVar("OUT2")
OUT3 = TypeVar("OUT3")
OUT4 = TypeVar("OUT4")
OUT5 = TypeVar("OUT5")
OUT6 = TypeVar("OUT6")
OUT_T = TypeVarTuple("OUT_T")
OUT_co = TypeVar("OUT_co", covariant=True)
OUT2_co = TypeVar("OUT2_co", covariant=True)

P = ParamSpec("P")

T = TypeVar("T")


def noop(val: T) -> T:
    return val


def line_info_at(stream: str, index: int) -> Tuple[int, int]:
    if index > len(stream):
        raise ValueError("invalid index")
    line = stream.count("\n", 0, index)
    last_nl = stream.rfind("\n", 0, index)
    col = index - (last_nl + 1)
    return (line, col)


# @dataclass
# class Stream:
#     stream: str

#     def at_index(self, index: int):
#         return memoryview(self.stream)


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
class Result(Generic[OUT_co]):
    status: bool
    index: int
    value: OUT_co
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


class Parser(Generic[OUT_co]):
    """
    A Parser is an object that wraps a function whose arguments are
    a string to be parsed and the index on which to begin parsing.
    The function should return either Result.success(next_index, value),
    where the next index is where to continue the parse and the value is
    the yielded value, or Result.failure(index, expected), where expected
    is a string indicating what was expected, and the index is the index
    of the failure.
    """

    def __init__(self, wrapped_fn: Callable[[str, int], Result[OUT_co]]):
        self.wrapped_fn: Callable[[str, int], Result[OUT_co]] = wrapped_fn

    def __call__(self, stream: str, index: int) -> Result[OUT_co]:
        return self.wrapped_fn(stream, index)

    def parse(self, stream: str) -> OUT_co:
        """Parse a string and return the result or raise a ParseError."""
        (result, _) = (self << eof).parse_partial(stream)
        return result

    def parse_partial(self, stream: str) -> Tuple[OUT_co, str]:
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

    def concat(self: Parser[List[str]]) -> Parser[str]:
        return self.map("".join)

    def then(self: Parser[Any], other: Parser[OUT2]) -> Parser[OUT2]:
        return (self & other).map(lambda t: t[1])

    def skip(self: Parser[OUT1], other: Parser[Any]) -> Parser[OUT1]:
        return (self & other).map(lambda t: t[0])

    def result(self: Parser[Any], res: OUT2) -> Parser[OUT2]:
        return self >> success(res)

    def many(self: Parser[OUT_co]) -> Parser[List[OUT_co]]:
        return self.times(0, float("inf"))

    def times(self: Parser[OUT_co], min: int, max: int | float | None = None) -> Parser[List[OUT_co]]:
        the_max: int | float
        if max is None:
            the_max = min
        else:
            the_max = max

        # TODO - must execute at least once
        @Parser
        def times_parser(stream: str, index: int) -> Result[List[OUT_co]]:
            values: List[OUT_co] = []
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

    def at_most(self: Parser[OUT_co], n: int) -> Parser[List[OUT_co]]:
        return self.times(0, n)

    def at_least(self: Parser[OUT_co], n: int) -> Parser[List[OUT_co]]:
        return self.times(min=n, max=float("inf"))

    @overload
    def optional(self: Parser[OUT1], default: None = None) -> Parser[OUT1 | None]:
        pass

    @overload
    def optional(self: Parser[OUT1], default: OUT2) -> Parser[OUT1 | OUT2]:
        pass

    def optional(self: Parser[OUT1], default: OUT2 | None = None) -> Parser[OUT1 | OUT2 | None]:
        return self.times(0, 1).map(lambda v: v[0] if v else default)

    def until(
        self: Parser[OUT_co],
        other: Parser[Any],
        min: int = 0,
        max: int | float = float("inf"),
        consume_other: bool = False,
    ) -> Parser[List[OUT_co]]:
        @Parser
        def until_parser(stream: str, index: int) -> Result[List[OUT_co]]:
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

    def sep_by(
        self: Parser[OUT_co], sep: Parser[Any], *, min: int = 0, max: int | float = float("inf")
    ) -> Parser[List[OUT_co]]:
        zero_times: Parser[List[OUT_co]] = success([])
        if max == 0:
            return zero_times
        # TODO
        res = (self & (sep >> self).times(min - 1, max - 1)).map(lambda t: [t[0], *t[1]])
        if min == 0:
            res = res | zero_times
        return res

    def desc(self, description: str) -> Parser[OUT_co]:
        @Parser
        def desc_parser(stream: str, index: int) -> Result[OUT_co]:
            result = self(stream, index)
            if result.status:
                return result
            else:
                return Result.failure(index, description)

        return desc_parser

    def mark(self: Parser[OUT_co]) -> Parser[Tuple[Tuple[int, int], OUT_co, Tuple[int, int]]]:
        return seq(line_info, self, line_info)

    def tag(self: Parser[OUT], name: str) -> Parser[Tuple[str, OUT]]:
        return self.map(lambda v: (name, v))

    def should_fail(self: Parser[OUT], description: str) -> Parser[Result[OUT]]:
        @Parser
        def fail_parser(stream: str, index: int) -> Result[Result[OUT]]:
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

    def __mul__(self: Parser[OUT], other: range | int) -> Parser[List[OUT]]:
        if isinstance(other, range):
            return self.times(other.start, other.stop - 1)
        return self.times(other)

    def __or__(self: Parser[OUT1], other: Parser[OUT2]) -> Parser[Union[OUT1, OUT2]]:
        @Parser
        def alt_parser(stream: str, index: int) -> Result[Union[OUT1, OUT2]]:
            result0 = None

            result1 = self(stream, index).aggregate(result0)
            if result1.status:
                return result1

            result2 = other(stream, index).aggregate(result1)
            return result2

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

    def join(self: Parser[OUT1], other: Parser[OUT2]) -> Parser[tuple[OUT1, OUT2]]:
        """TODO alternative name for `&`, decide on naming"""
        return self & other

    def as_tuple(self: Parser[OUT]) -> Parser[Tuple[OUT]]:
        return self.map(lambda value: (value,))

    def append(self: Parser[Tuple[Unpack[OUT_T]]], other: Parser[OUT2]) -> Parser[Tuple[Unpack[OUT_T], OUT2]]:
        """
        Take a parser which produces a tuple of values, and add another parser's result
        to the end of that tuples
        """
        return self.bind(lambda self_value: other.bind(lambda other_value: success((*self_value, other_value))))

    def combine(self: Parser[Tuple[Unpack[OUT_T]]], combine_fn: Callable[[Unpack[OUT_T]], OUT2]) -> Parser[OUT2]:
        """
        Apply ``combine_fn`` to the parser result, which must be a tuple. The result
        is passed as `*args` to ``combine_fn``.
        """
        return self.bind(lambda value: success(combine_fn(*value)))

    # haskelley operators, for fun #

    # >>

    def __rshift__(self, other: Parser[OUT]) -> Parser[OUT]:
        return self.then(other)

    # <<
    def __lshift__(self, other: Parser[Any]) -> Parser[OUT_co]:
        return self.skip(other)


# TODO:
# I think @generate is unfixable. It's not surprising, because
# we are doing something genuninely unusual with generator functions.

# The return value of a `@generate` parser is now OK.

# But we have no type checking within a user's @generate function.

# The big issue is that each `val = yield parser` inside a @generate parser has
# a different type, and we'd like those to be typed checked. But the
# `Generator[...]` expects a homogeneous stream of yield and send types,
# whereas we have pairs of yield/send types which need to match within the
# pair, but each pair can be completely different from the next in the stream


def generate(fn: Callable[[], Generator[Parser[Any], Any, OUT]]) -> Parser[OUT]:
    @Parser
    @wraps(fn)
    def generated(stream: str, index: int) -> Result[OUT]:
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
    def string_parser(stream: str, index: int) -> Result[str]:
        if transform(stream[index : index + slen]) == transformed_s:
            return Result.success(index + slen, s)
        else:
            return Result.failure(index, s)

    return string_parser

PatternType = Union[str, re.Pattern[str]]

@overload
def regex(
    pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: Literal[0] = 0
) -> Parser[str]:
    ...


@overload
def regex(
    pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: str | int
) -> Parser[str]:
    ...


@overload
def regex(
    pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: Tuple[str | int]
) -> Parser[Tuple[str]]:
    ...


@overload
def regex(
    pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: Tuple[str | int, str | int]
) -> Parser[Tuple[str, str]]:
    ...

@overload
def regex(
    pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: Tuple[str | int, str | int, str | int]
) -> Parser[Tuple[str, str, str]]:
    ...

@overload
def regex(
    pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: Tuple[str | int, str | int, str | int, str | int]
) -> Parser[Tuple[str, str, str, str]]:
    ...

@overload
def regex(
    pattern: PatternType, *, flags: re.RegexFlag = re.RegexFlag(0), group: Tuple[str | int, str | int, str | int, str | int, str | int]
) -> Parser[Tuple[str, str, str, str, str]]:
    ...


def regex(
    pattern: PatternType,
    *,
    flags: re.RegexFlag = re.RegexFlag(0),
    group: str | int | Tuple[str | int, ...] = 0,
) -> Parser[str | Tuple[str, ...]]:
    if isinstance(pattern, str):
        exp = re.compile(pattern, flags)
    else:
        exp = pattern

    if isinstance(group, tuple) and len(group) >= 2:
        first_group, second_group, *groups = group

        @Parser
        def regex_parser_tuple(stream: str, index: int) -> Result[Tuple[str, ...]]:
            match = exp.match(stream, index)
            if match:
                match_result = match.group(first_group, second_group, *groups)
                return Result.success(match.end(), match_result)
            else:
                return Result.failure(index, exp.pattern)

        return regex_parser_tuple

    if isinstance(group, tuple) and len(group) == 1:
        target_group = group[0]
    elif isinstance(group, tuple):
        target_group = 0
    else:
        target_group = group

    @Parser
    def regex_parser(stream: str, index: int) -> Result[str]:
        match = exp.match(stream, index)
        if match:
            return Result.success(match.end(), match.group(target_group))
        else:
            return Result.failure(index, exp.pattern)

    return regex_parser


# Each number of args needs to be typed separately
@overload
def seq(
    __arg1: Parser[OUT1],
    __arg2: Parser[OUT2],
    __arg3: Parser[OUT3],
    __arg4: Parser[OUT4],
    __arg5: Parser[OUT5],
    __arg6: Parser[OUT6],
) -> Parser[Tuple[OUT1, OUT2, OUT3, OUT4, OUT5, OUT6]]:
    ...


@overload
def seq(
    __arg1: Parser[OUT1], __arg2: Parser[OUT2], __arg3: Parser[OUT3], __arg4: Parser[OUT4], __arg5: Parser[OUT5]
) -> Parser[Tuple[OUT1, OUT2, OUT3, OUT4, OUT5]]:
    ...


@overload
def seq(
    __arg1: Parser[OUT1], __arg2: Parser[OUT2], __arg3: Parser[OUT3], __arg4: Parser[OUT4]
) -> Parser[Tuple[OUT1, OUT2, OUT3, OUT4]]:
    ...


@overload
def seq(__arg1: Parser[OUT1], __arg2: Parser[OUT2], __arg3: Parser[OUT3]) -> Parser[Tuple[OUT1, OUT2, OUT3]]:
    ...


@overload
def seq(__arg1: Parser[OUT1], __arg2: Parser[OUT2]) -> Parser[Tuple[OUT1, OUT2]]:
    ...


@overload
def seq(__arg1: Parser[OUT1]) -> Parser[Tuple[OUT1]]:
    ...


@overload
def seq(*args: Parser[Any]) -> Parser[Tuple[Any, ...]]:
    ...


def seq(*args: Parser[Any]) -> Parser[Tuple[Any, ...]]:
    if not args:
        raise ValueError()
    first, *remainder = args
    parser = first.as_tuple()
    for p in remainder:
        parser = parser.append(p)  # type: ignore
    return parser


# TODO the rest of the functions here need type annotations.

# One problem is that `test_item` and `match_item` are assumning that the input
# type might not be str, but arbitrary types, including heterogeneous
# lists. We have no generic parameter for the input stream type
# yet, for simplicity.


def test_char(func: Callable[[str], bool], description: str) -> Parser[str]:
    @Parser
    def test_char_parser(stream: str, index: int) -> Result[str]:
        if index < len(stream):
            if func(stream[index]):
                return Result.success(index + 1, stream[index])
        return Result.failure(index, description)

    return test_char_parser


def match_char(char: str, description: Optional[str] = None) -> Parser[str]:
    if description is None:
        description = char
    return test_char(lambda i: char == i, description)


def string_from(*strings: str, transform: Callable[[str], str] = noop) -> Parser[str]:
    # Sort longest first, so that overlapping options work correctly
    return reduce(operator.or_, [string(s, transform) for s in sorted(strings, key=len, reverse=True)])


# TODO drop bytes support here
def char_from(string: str) -> Parser[str]:
    return test_char(lambda c: c in string, "[" + string + "]")


def peek(parser: Parser[OUT]) -> Parser[OUT]:
    @Parser
    def peek_parser(stream: str, index: int) -> Result[OUT]:
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


def from_enum(enum_cls: type[E], transform: Callable[[str], str] = noop) -> Parser[E]:
    items = sorted(
        ((str(enum_item.value), enum_item) for enum_item in enum_cls), key=lambda t: len(t[0]), reverse=True
    )
    return reduce(operator.or_, [string(value, transform=transform).result(enum_item) for value, enum_item in items])


# TODO how do we type a forward_declaration instance? For a typical usage, see
# examples/json.py. I think this is probably a recursive type issue which is probably
# mirroring the recursive definition issues that forward_declaration is designed to solve.
# Cutting the recursive knot might be harder at the type level?


class forward_declaration(Parser[OUT]):
    """
    An empty parser that can be used as a forward declaration,
    especially for parsers that need to be defined recursively.

    You must use `.become(parser)` before using.
    """

    def __init__(self) -> None:
        pass

    def _raise_error(self, *args: Any, **kwargs: Any) -> Any:
        raise ValueError("You must use 'become' before attempting to call `parse` or `parse_partial`")

    parse = _raise_error
    parse_partial = _raise_error

    def become(self, other: Parser[OUT2]) -> Parser[OUT2]:
        self.__dict__ = other.__dict__
        self.__class__ = other.__class__
        self = cast(Parser[OUT2], self)
        return self


# Dataclass parsers


def parse_field(
    parser: Parser[OUT],
    *,
    default: OUT = ...,
    init: bool = ...,
    repr: bool = ...,
    hash: Union[bool, None] = ...,
    compare: bool = ...,
    metadata: Mapping[Any, Any] = ...,
) -> OUT:
    if metadata is Ellipsis:
        metadata = {}
    return field(
        default=default, init=init, repr=repr, hash=hash, compare=compare, metadata={**metadata, "parser": parser}
    )


class DataClassProtocol(Protocol):
    __dataclass_fields__: ClassVar[Dict[str, Field[Any]]]
    __init__: Callable


OUT_D = TypeVar("OUT_D", bound=DataClassProtocol)


def dataparser(datatype: Type[OUT_D]) -> Parser[OUT_D]:
    @Parser
    def data_parser(stream: str, index: int) -> Result[OUT_D]:
        parsed_fields: Dict[str, Any] = {}
        result = Result.success(index, None)
        for field in fields(datatype):
            if "parser" not in field.metadata:
                continue
            parser: Parser[Any] = field.metadata["parser"]
            result = parser(stream, index)
            if not result.status:
                return result  # type: ignore
            index = result.index
            parsed_fields[field.name] = result.value

        return Result.success(result.index, datatype(**parsed_fields))

    return data_parser
