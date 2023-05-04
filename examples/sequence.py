from dataclasses import dataclass
from typing import TypeVar

from typing_extensions import TypeVarTuple

from parsy import regex, seq, whitespace


@dataclass
class Person:
    name: str
    age: int
    note: str

person_arg_sequence = seq(
    regex(r"\w+"),
    whitespace >> regex(r"\d+").map(int),
    whitespace >> regex(r".+"),
)
person_parser = person_arg_sequence.combine(Person)

person = person_parser.parse("Rob 1000 pretty old")

print(person)

assert person == Person(name="Rob", age=1000, note="pretty old")
