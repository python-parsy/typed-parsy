from dataclasses import dataclass
from typing import TypeVar

from typing_extensions import TypeVarTuple

from parsy import regex, seq, whitespace

OUT1 = TypeVar("OUT1")
OUT2 = TypeVar("OUT2")
OUT3 = TypeVar("OUT3")
OUT4 = TypeVar("OUT4")
OUT5 = TypeVar("OUT5")
OUT6 = TypeVar("OUT6")
OUT_T = TypeVarTuple("OUT_T")


@dataclass
class Person:
    name: str
    age: int
    note: str


person_parser = seq(
    regex(r"\w+"),
    whitespace >> regex(r"\d+").map(int),
    whitespace >> regex(r".+"),
).combine(Person)

person = person_parser.parse("Rob 1000 pretty old")

print(person)

assert person == Person(name="Rob", age=1000, note="pretty old")
