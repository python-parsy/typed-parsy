from typing import TypeVar

from parsy import Parser, forward_declaration, regex, string

# Utilities
whitespace = regex(r"\s*")

T = TypeVar("T")


def lexeme(p: Parser[T]) -> Parser[T]:
    return p << whitespace


# Punctuation
lbrace = lexeme(string("{"))
rbrace = lexeme(string("}"))
lbrack = lexeme(string("["))
rbrack = lexeme(string("]"))
colon = lexeme(string(":"))
comma = lexeme(string(","))

# Primitives
true = lexeme(string("true")).result(True)
false = lexeme(string("false")).result(False)
null = lexeme(string("null")).result(None)
number = lexeme(regex(r"-?(0|[1-9][0-9]*)([.][0-9]+)?([eE][+-]?[0-9]+)?")).map(float)
string_part = regex(r'[^"\\]+')
string_esc = string("\\") >> (
    string("\\")
    | string("/")
    | string('"')
    | string("b").result("\b")
    | string("f").result("\f")
    | string("n").result("\n")
    | string("r").result("\r")
    | string("t").result("\t")
    | regex(r"u[0-9a-fA-F]{4}").map(lambda s: chr(int(s[1:], 16)))
)
quoted = lexeme(string('"') >> (string_part | string_esc).many().concat() << string('"'))

# Data structures
JSON = TypeVar("JSON")

json_value = forward_declaration[JSON]()
object_pair = (quoted << colon) & json_value
json_object = lbrace >> object_pair.sep_by(comma).map(lambda a: {g[0]: g[1] for g in a}) << rbrace
array = lbrack >> json_value.sep_by(comma) << rbrack

# Everything
all = quoted | number | json_object | array | true | false | null
json_value = json_value.become(all)
json_doc = whitespace >> json_value

# JSON = Union[Dict[str, JSON], List[JSON], str, int, float, bool, None]


def test():
    result = json_doc.parse(
        r"""
    {
        "int": 1,
        "string": "hello",
        "a list": [1, 2, 3],
        "escapes": "\n \u24D2",
        "nested": {"x": "y"},
        "other": [true, false, null]
    }
"""
    )
    print(result)
    assert result == {
        "int": 1,
        "string": "hello",
        "a list": [1, 2, 3],
        "escapes": "\n ⓒ",
        "nested": {"x": "y"},
        "other": [True, False, None],
    }


if __name__ == "__main__":
    test()
    # print(repr(json_doc.parse(stdin.read())))
