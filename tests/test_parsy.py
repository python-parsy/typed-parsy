# -*- code: utf8 -*-
import enum
import re
import unittest
from typing import Any, Generator, Tuple

from parsy import (
    ParseError,
    Parser,
    Result,
    any_char,
    char_from,
    decimal_digit,
    digit,
    forward_declaration,
    from_enum,
    generate,
    index,
    letter,
    line_info,
    line_info_at,
    peek,
    regex,
    string,
    string_from,
)
from parsy import test_char as parsy_test_char  # to stop pytest thinking this function is a test
from parsy import whitespace


class TestParser(unittest.TestCase):
    def test_string(self):
        parser = string("x")
        self.assertEqual(parser.parse("x"), "x")

        self.assertRaises(ParseError, parser.parse, "y")

    def test_string_transform(self):
        parser = string("x", transform=lambda s: s.lower())
        self.assertEqual(parser.parse("x"), "x")
        self.assertEqual(parser.parse("X"), "x")

        self.assertRaises(ParseError, parser.parse, "y")

    def test_string_transform_2(self):
        parser = string("Cat", transform=lambda s: s.lower())
        self.assertEqual(parser.parse("cat"), "Cat")
        self.assertEqual(parser.parse("CAT"), "Cat")
        self.assertEqual(parser.parse("CaT"), "Cat")

        self.assertRaises(ParseError, parser.parse, "dog")

    def test_regex_str(self):
        parser = regex(r"[0-9]")

        self.assertEqual(parser.parse("1"), "1")
        self.assertEqual(parser.parse("4"), "4")

        self.assertRaises(ParseError, parser.parse, "x")

    # def test_regex_bytes(self):
    #     parser = regex(rb"[0-9]")

    #     self.assertEqual(parser.parse(b"1"), b"1")
    #     self.assertEqual(parser.parse(b"4"), b"4")

    #     self.assertRaises(ParseError, parser.parse, b"x")

    def test_regex_compiled(self):
        parser = regex(re.compile(r"[0-9]"))
        self.assertEqual(parser.parse("1"), "1")
        self.assertRaises(ParseError, parser.parse, "x")

    def test_regex_group_number(self):
        parser = regex(re.compile(r"a([0-9])b"), group=1)
        self.assertEqual(parser.parse("a1b"), "1")
        self.assertRaises(ParseError, parser.parse, "x")

    def test_regex_group_name(self):
        parser = regex(re.compile(r"a(?P<name>[0-9])b"), group="name")
        self.assertEqual(parser.parse("a1b"), "1")
        self.assertRaises(ParseError, parser.parse, "x")

    def test_regex_group_tuple(self):
        parser = regex(re.compile(r"a([0-9])b([0-9])c"), group=(1, 2))
        self.assertEqual(parser.parse("a1b2c"), ("1", "2"))
        self.assertRaises(ParseError, parser.parse, "x")

    def test_then(self):
        xy_parser = string("x") >> string("y")
        self.assertEqual(xy_parser.parse("xy"), "y")

        self.assertRaises(ParseError, xy_parser.parse, "y")
        self.assertRaises(ParseError, xy_parser.parse, "z")

    def test_bind(self):
        piped = None

        def binder(x):
            nonlocal piped
            piped = x
            return string("y")

        parser = string("x").bind(binder)

        self.assertEqual(parser.parse("xy"), "y")
        self.assertEqual(piped, "x")

        self.assertRaises(ParseError, parser.parse, "x")

    def test_map(self):
        parser = digit.map(int)
        self.assertEqual(parser.parse("7"), 7)

    def test_and(self):
        parser = digit & letter
        self.assertEqual(parser.parse("1A"), ("1", "A"))

    def test_append(self):
        parser = digit.join(letter).append(letter)
        self.assertEqual(parser.parse("1AB"), ("1", "A", "B"))

    def test_combine(self):
        parser = digit.join(letter).append(letter).combine(lambda a, b, c: (c + b + a))
        self.assertEqual(parser.parse("1AB"), "BA1")

    # def test_combine_mixed_types(self):
    #     def demo(a: int, b: str, c: bool) -> Tuple[int, str, bool]:
    #         return (a, b, c)

    #     parser = digit.map(int).join(letter).append(digit.map(bool)).combine(demo)
    #     self.assertEqual(parser.parse("1A1"), (1, "A", True))

    def test_concat(self):
        parser = letter.many().concat()
        self.assertEqual(parser.parse(""), "")
        self.assertEqual(parser.parse("abc"), "abc")

    def test_generate(self):
        x = y = None

        @generate
        def xy() -> Generator[Parser[Any], Any, int]:
            nonlocal x
            nonlocal y
            x = yield string("x")
            y = yield string("y")
            return 3

        self.assertEqual(xy.parse("xy"), 3)
        self.assertEqual(x, "x")
        self.assertEqual(y, "y")

    def test_mark(self):
        parser = (letter.many().mark() << string("\n")).many()

        lines = parser.parse("asdf\nqwer\n")

        self.assertEqual(len(lines), 2)

        (start, letters, end) = lines[0]
        self.assertEqual(start, (0, 0))
        self.assertEqual(letters, ["a", "s", "d", "f"])
        self.assertEqual(end, (0, 4))

        (start, letters, end) = lines[1]
        self.assertEqual(start, (1, 0))
        self.assertEqual(letters, ["q", "w", "e", "r"])
        self.assertEqual(end, (1, 4))

    def test_tag(self):
        parser = letter.many().concat().tag("word")
        self.assertEqual(
            parser.sep_by(string(",")).parse("this,is,a,list"),
            [("word", "this"), ("word", "is"), ("word", "a"), ("word", "list")],
        )

    def test_multiple_failures(self):
        abc = string("a") | string("b") | string("c")

        with self.assertRaises(ParseError) as err:
            abc.parse("d")

        ex = err.exception
        self.assertEqual(ex.expected, frozenset(["a", "b", "c"]))
        self.assertEqual(str(ex), "expected one of 'a', 'b', 'c' at 0:0")

    def test_generate_backtracking(self):
        @generate
        def xy() -> Generator[Parser[Any], Any, None]:
            yield string("x")
            yield string("y")
            assert False

        parser = xy | string("z")
        # should not finish executing xy()
        self.assertEqual(parser.parse("z"), "z")

    def test_or(self):
        x_or_y = string("x") | string("y")

        self.assertEqual(x_or_y.parse("x"), "x")
        self.assertEqual(x_or_y.parse("y"), "y")

    def test_or_with_then(self):
        parser = (string("\\") >> string("y")) | string("z")
        self.assertEqual(parser.parse("\\y"), "y")
        self.assertEqual(parser.parse("z"), "z")

        self.assertRaises(ParseError, parser.parse, "\\z")

    def test_many(self):
        letters = letter.many()
        self.assertEqual(letters.parse("x"), ["x"])
        self.assertEqual(letters.parse("xyz"), ["x", "y", "z"])
        self.assertEqual(letters.parse(""), [])

        self.assertRaises(ParseError, letters.parse, "1")

    def test_many_with_then(self):
        parser = string("x").many() >> string("y")
        self.assertEqual(parser.parse("y"), "y")
        self.assertEqual(parser.parse("xy"), "y")
        self.assertEqual(parser.parse("xxxxxy"), "y")

    def test_times_zero(self):
        zero_letters = letter.times(0)
        self.assertEqual(zero_letters.parse(""), [])

        self.assertRaises(ParseError, zero_letters.parse, "x")

    def test_times(self):
        three_letters = letter.times(3)
        self.assertEqual(three_letters.parse("xyz"), ["x", "y", "z"])

        self.assertRaises(ParseError, three_letters.parse, "xy")
        self.assertRaises(ParseError, three_letters.parse, "xyzw")

    def test_times_with_then(self):
        then_digit = letter.times(3) >> digit
        self.assertEqual(then_digit.parse("xyz1"), "1")

        self.assertRaises(ParseError, then_digit.parse, "xy1")
        self.assertRaises(ParseError, then_digit.parse, "xyz")
        self.assertRaises(ParseError, then_digit.parse, "xyzw")

    def test_times_with_min_and_max(self):
        some_letters = letter.times(2, 4)

        self.assertEqual(some_letters.parse("xy"), ["x", "y"])
        self.assertEqual(some_letters.parse("xyz"), ["x", "y", "z"])
        self.assertEqual(some_letters.parse("xyzw"), ["x", "y", "z", "w"])

        self.assertRaises(ParseError, some_letters.parse, "x")
        self.assertRaises(ParseError, some_letters.parse, "xyzwv")

    def test_times_with_min_and_max_and_then(self):
        then_digit = letter.times(2, 4) >> digit

        self.assertEqual(then_digit.parse("xy1"), "1")
        self.assertEqual(then_digit.parse("xyz1"), "1")
        self.assertEqual(then_digit.parse("xyzw1"), "1")

        self.assertRaises(ParseError, then_digit.parse, "xy")
        self.assertRaises(ParseError, then_digit.parse, "xyzw")
        self.assertRaises(ParseError, then_digit.parse, "xyzwv1")
        self.assertRaises(ParseError, then_digit.parse, "x1")

    def test_at_most(self):
        ab = string("ab")
        self.assertEqual(ab.at_most(2).parse(""), [])
        self.assertEqual(ab.at_most(2).parse("ab"), ["ab"])
        self.assertEqual(ab.at_most(2).parse("abab"), ["ab", "ab"])
        self.assertRaises(ParseError, ab.at_most(2).parse, "ababab")

    def test_at_least(self):
        ab = string("ab")
        self.assertEqual(ab.at_least(2).parse("abab"), ["ab", "ab"])
        self.assertEqual(ab.at_least(2).parse("ababab"), ["ab", "ab", "ab"])
        self.assertRaises(ParseError, ab.at_least(2).parse, "ab")
        self.assertEqual(ab.at_least(2).parse_partial("abababc"), (["ab", "ab", "ab"], "c"))

    def test_until(self):
        until = string("s").until(string("x"))

        s = "ssssx"
        self.assertEqual(until.parse_partial(s), (4 * ["s"], "x"))
        self.assertEqual(until.then(string("x")).parse(s), "x")

        s = "ssssxy"
        self.assertEqual(until.parse_partial(s), (4 * ["s"], "xy"))
        self.assertEqual(until.then(string("x")).parse_partial(s), ("x", "y"))

        self.assertRaises(ParseError, until.parse, "ssssy")
        self.assertRaises(ParseError, until.parse, "xssssxy")

        self.assertEqual(until.parse_partial("xxx"), ([], "xxx"))

        until = regex(".").until(string("x"))
        self.assertEqual(until.parse_partial("xxxx"), ([], "xxxx"))

    def test_until_with_consume_other(self):
        until = string("s").until(string("x"), consume_other=True)

        self.assertEqual(until.parse("ssssx"), 4 * ["s"] + ["x"])
        self.assertEqual(until.parse_partial("ssssxy"), (4 * ["s"] + ["x"], "y"))

        self.assertEqual(until.parse_partial("xxx"), (["x"], "xx"))

        self.assertRaises(ParseError, until.parse, "ssssy")
        self.assertRaises(ParseError, until.parse, "xssssxy")

    def test_until_with_min(self):
        until = string("s").until(string("x"), min=3)

        self.assertEqual(until.parse_partial("sssx"), (3 * ["s"], "x"))
        self.assertEqual(until.parse_partial("sssssx"), (5 * ["s"], "x"))

        self.assertRaises(ParseError, until.parse_partial, "ssx")

    def test_until_with_max(self):
        # until with max
        until = string("s").until(string("x"), max=3)

        self.assertEqual(until.parse_partial("ssx"), (2 * ["s"], "x"))
        self.assertEqual(until.parse_partial("sssx"), (3 * ["s"], "x"))

        self.assertRaises(ParseError, until.parse_partial, "ssssx")

    def test_until_with_min_max(self):
        until = string("s").until(string("x"), min=3, max=5)

        self.assertEqual(until.parse_partial("sssx"), (3 * ["s"], "x"))
        self.assertEqual(until.parse_partial("sssssx"), (5 * ["s"], "x"))

        with self.assertRaises(ParseError) as cm:
            until.parse_partial("ssx")
        assert cm.exception.args[0] == frozenset({"at least 3 items; got 2 item(s)"})
        with self.assertRaises(ParseError) as cm:
            until.parse_partial("ssssssx")
        assert cm.exception.args[0] == frozenset({"at most 5 items"})

    def test_optional(self):
        p = string("a").optional()
        self.assertEqual(p.parse("a"), "a")
        self.assertEqual(p.parse(""), None)
        p = string("a").optional("b")
        self.assertEqual(p.parse("a"), "a")
        self.assertEqual(p.parse(""), "b")

    def test_sep_by(self):
        digit_list = digit.map(int).sep_by(string(","))

        self.assertEqual(digit_list.parse("1,2,3,4"), [1, 2, 3, 4])
        self.assertEqual(digit_list.parse("9,0,4,7"), [9, 0, 4, 7])
        self.assertEqual(digit_list.parse("3,7"), [3, 7])
        self.assertEqual(digit_list.parse("8"), [8])
        self.assertEqual(digit_list.parse(""), [])

        self.assertRaises(ParseError, digit_list.parse, "8,")
        self.assertRaises(ParseError, digit_list.parse, ",9")
        self.assertRaises(ParseError, digit_list.parse, "82")
        self.assertRaises(ParseError, digit_list.parse, "7.6")

    def test_sep_by_with_min_and_max(self):
        digit_list = digit.map(int).sep_by(string(","), min=2, max=4)

        self.assertEqual(digit_list.parse("1,2,3,4"), [1, 2, 3, 4])
        self.assertEqual(digit_list.parse("9,0,4,7"), [9, 0, 4, 7])
        self.assertEqual(digit_list.parse("3,7"), [3, 7])

        self.assertRaises(ParseError, digit_list.parse, "8")
        self.assertRaises(ParseError, digit_list.parse, "")
        self.assertRaises(ParseError, digit_list.parse, "8,")
        self.assertRaises(ParseError, digit_list.parse, ",9")
        self.assertRaises(ParseError, digit_list.parse, "82")
        self.assertRaises(ParseError, digit_list.parse, "7.6")
        self.assertEqual(digit.sep_by(string(","), max=0).parse(""), [])

    def test_add(self):
        self.assertEqual((letter + digit).parse("a1"), "a1")

    def test_multiply(self):
        self.assertEqual((letter * 3).parse("abc"), ["a", "b", "c"])

    def test_multiply_range(self):
        self.assertEqual((letter * range(1, 2)).parse("a"), ["a"])
        self.assertRaises(ParseError, (letter * range(1, 2)).parse, "aa")

    # Primitives

    def test_test_char(self):
        ascii = parsy_test_char(lambda c: ord(c) < 128, "ascii character")
        self.assertEqual(ascii.parse("a"), "a")
        with self.assertRaises(ParseError) as err:
            ascii.parse("☺")
        ex = err.exception
        self.assertEqual(str(ex), """expected 'ascii character' at 0:0""")

        with self.assertRaises(ParseError) as err:
            ascii.parse("")
        ex = err.exception
        self.assertEqual(str(ex), """expected 'ascii character' at 0:0""")

    def test_char_from_str(self):
        ab = char_from("ab")
        self.assertEqual(ab.parse("a"), "a")
        self.assertEqual(ab.parse("b"), "b")

        with self.assertRaises(ParseError) as err:
            ab.parse("x")

        ex = err.exception
        self.assertEqual(str(ex), """expected '[ab]' at 0:0""")

    # def test_char_from_bytes(self):
    #     ab = char_from(b"ab")
    #     self.assertEqual(ab.parse(b"a"), b"a")
    #     self.assertEqual(ab.parse(b"b"), b"b")

    #     with self.assertRaises(ParseError) as err:
    #         ab.parse(b"x")

    #     ex = err.exception
    #     self.assertEqual(str(ex), """expected b'[ab]' at 0""")

    def test_string_from(self):
        titles = string_from("Mr", "Mr.", "Mrs", "Mrs.")
        self.assertEqual(titles.parse("Mr"), "Mr")
        self.assertEqual(titles.parse("Mr."), "Mr.")
        self.assertEqual((titles + string(" Hyde")).parse("Mr. Hyde"), "Mr. Hyde")
        with self.assertRaises(ParseError) as err:
            titles.parse("foo")

        ex = err.exception
        self.assertEqual(str(ex), """expected one of 'Mr', 'Mr.', 'Mrs', 'Mrs.' at 0:0""")

    def test_string_from_transform(self):
        titles = string_from("Mr", "Mr.", "Mrs", "Mrs.", transform=lambda s: s.lower())
        self.assertEqual(titles.parse("mr"), "Mr")
        self.assertEqual(titles.parse("mr."), "Mr.")
        self.assertEqual(titles.parse("MR"), "Mr")
        self.assertEqual(titles.parse("MR."), "Mr.")

    def test_peek(self):
        self.assertEqual(peek(any_char).parse_partial("abc"), ("a", "abc"))
        with self.assertRaises(ParseError) as err:
            peek(digit).parse("a")
        self.assertEqual(str(err.exception), "expected 'a digit' at 0:0")

    def test_any_char(self):
        self.assertEqual(any_char.parse("x"), "x")
        self.assertEqual(any_char.parse("\n"), "\n")
        self.assertRaises(ParseError, any_char.parse, "")

    def test_whitespace(self):
        self.assertEqual(whitespace.parse("\n"), "\n")
        self.assertEqual(whitespace.parse(" "), " ")
        self.assertRaises(ParseError, whitespace.parse, "x")

    def test_letter(self):
        self.assertEqual(letter.parse("a"), "a")
        self.assertRaises(ParseError, letter.parse, "1")

    def test_digit(self):
        self.assertEqual(digit.parse("¹"), "¹")
        self.assertEqual(digit.parse("2"), "2")
        self.assertRaises(ParseError, digit.parse, "x")

    def test_decimal_digit(self):
        self.assertEqual(decimal_digit.at_least(1).concat().parse("9876543210"), "9876543210")
        self.assertRaises(ParseError, decimal_digit.parse, "¹")

    def test_line_info(self):
        @generate
        def foo() -> Generator[Any, Any, Tuple[str, Tuple[int, int]]]:
            i = yield line_info
            l = yield any_char
            return (l, i)

        self.assertEqual(
            foo.many().parse("AB\nCD"),
            [
                ("A", (0, 0)),
                ("B", (0, 1)),
                ("\n", (0, 2)),
                ("C", (1, 0)),
                ("D", (1, 1)),
            ],
        )

    def test_should_fail(self):
        not_a_digit = digit.should_fail("not a digit") >> regex(r".*")

        self.assertEqual(not_a_digit.parse("a"), "a")
        self.assertEqual(not_a_digit.parse("abc"), "abc")
        self.assertEqual(not_a_digit.parse("a10"), "a10")
        self.assertEqual(not_a_digit.parse(""), "")

        with self.assertRaises(ParseError) as err:
            not_a_digit.parse("8")
        self.assertEqual(str(err.exception), "expected 'not a digit' at 0:0")

        self.assertRaises(ParseError, not_a_digit.parse, "8ab")

    def test_should_fail_isolated(self):
        not_a_digit = digit.should_fail("not a digit")

        self.assertEqual(
            not_a_digit.parse_partial("a"),
            (Result(status=False, index=-1, value=None, furthest=0, expected=frozenset({"a digit"})), "a"),
        )
        self.assertRaises(ParseError, not_a_digit.parse_partial, "1")

    def test_from_enum_string(self):
        class Pet(enum.Enum):
            CAT = "cat"
            DOG = "dog"

        pet = from_enum(Pet)
        self.assertEqual(pet.parse("cat"), Pet.CAT)
        self.assertEqual(pet.parse("dog"), Pet.DOG)
        self.assertRaises(ParseError, pet.parse, "foo")

        def test_from_enum_int(self):
            class Position(enum.Enum):
                FIRST = 1
                SECOND = 2

            position = from_enum(Position)
            self.assertEqual(position.parse("1"), Position.FIRST)
            self.assertEqual(position.parse("2"), Position.SECOND)
            self.assertRaises(ParseError, position.parse, "foo")

        def test_from_enum_transform(self):
            class Pet(enum.Enum):
                CAT = "cat"
                DOG = "dog"

            pet = from_enum(Pet, transform=lambda s: s.lower())
            self.assertEqual(pet.parse("cat"), Pet.CAT)
            self.assertEqual(pet.parse("CAT"), Pet.CAT)


class TestUtils(unittest.TestCase):
    def test_line_info_at(self):
        text = "abc\ndef"
        self.assertEqual(line_info_at(text, 0), (0, 0))
        self.assertEqual(line_info_at(text, 2), (0, 2))
        self.assertEqual(line_info_at(text, 3), (0, 3))
        self.assertEqual(line_info_at(text, 4), (1, 0))
        self.assertEqual(line_info_at(text, 7), (1, 3))
        self.assertRaises(ValueError, lambda: line_info_at(text, 8))


class TestForwardDeclaration(unittest.TestCase):
    def test_forward_declaration_1(self):
        # This is the example from the docs
        expr = forward_declaration()
        with self.assertRaises(ValueError):
            expr.parse("()")

        with self.assertRaises(ValueError):
            expr.parse_partial("()")

        simple = regex("[0-9]+").map(int)
        group = string("(") >> expr.sep_by(string(" ")) << string(")")
        expr.become(simple | group)

        self.assertEqual(expr.parse("(0 1 (2 3))"), [0, 1, [2, 3]])

    def test_forward_declaration_2(self):
        # Simplest example I could think of
        expr = forward_declaration()
        expr.become(string("A") + expr | string("Z"))

        self.assertEqual(expr.parse("Z"), "Z")
        self.assertEqual(expr.parse("AZ"), "AZ")
        self.assertEqual(expr.parse("AAAAAZ"), "AAAAAZ")

        with self.assertRaises(ParseError):
            expr.parse("A")

        with self.assertRaises(ParseError):
            expr.parse("B")

        self.assertEqual(expr.parse_partial("AAZXX"), ("AAZ", "XX"))

    def test_forward_declaration_cant_become_twice(self):
        dec = forward_declaration()
        other = string("X")
        dec.become(other)

        with self.assertRaises((AttributeError, TypeError)):
            dec.become(other)


if __name__ == "__main__":
    unittest.main()
