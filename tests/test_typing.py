# Attempt to add type annotations to Parsy.
#
# In the simplest case, a type checker could check that we are using only
# methods that exist on `Parser` instances, like `parse` and `parse_partial`.
# That's not hugely useful, however.
#
# In reality, `Parser` instances are generic in what they produce.
# (We'll ignore polymorphism in input type, and assume we only consume `str`)
#
# For example, `string("xxx")` is a `Parser` whose `parse` method will produce
# a `str`.
# However, `string("123").map(int)` is a `Parser` whose `parse` method will produce
# an `int`.
#
# `string("123").map(int) << string(",")` also produces `int`

# With appropriate type definitions on `map`, `__lshift__` etc. methods, we can
# get this to work:

from dataclasses import dataclass

import parsy


@dataclass
class Foo:
    val: int


# mypy correctly accepts these:
good_type: str = parsy.string("test").parse("test")
good_type2: int = parsy.string("123").map(int).parse("123")
good_type3: Foo = (parsy.regex(r"\d+").map(int).map(Foo) << parsy.string("x")).parse("123x")

# and it correctly rejects these, with sensible error messages:
bad_type: int = parsy.string("test").parse("test")
bad_type2: int = parsy.string("test").map(str).parse("test")
bad_type3: str = parsy.string("123").map(int).parse("123")
bad_type4: Foo = (parsy.regex(r"\d+").map(int).map(Foo) >> parsy.string("x")).parse("123x")

# This should also be rejected, without having to call "parse"
bad_parser = parsy.regex(r"\d+").map(Foo)


@dataclass
class Pair:
    key: str
    val: int


pair = ((parsy.regex("[a-z]+") << parsy.string("=")) & parsy.regex(r"\d+").map(int)).map(lambda t: Pair(t[0], t[1]))

good_type4: Pair = pair.parse("x=123")

bad_type5: Foo = pair.parse("x=123")  # should be Pair not Foo

# this is missing a `map(int)`, incompatible with Pair.val, so should be rejected.
bad_pair = ((parsy.regex("[a-z]+") << parsy.string("=")) & parsy.regex(r"\d+")).map(lambda t: Pair(t[0], t[1]))
