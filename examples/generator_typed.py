


from dataclasses import dataclass
from typing import Generator, Union
from parsy import Parser, generate, regex, success, whitespace


@dataclass
class Person:
    name: str
    age: int
    note: str


def person_parser():
    @generate
    def person_parser() -> Generator[Parser[str], str, Person]:
        # By yielding parsers of a single type, the type system works.
        # Homogeneous generator types don't exist.
        name = yield regex(r"\w+") << whitespace

        # But every parser starts by matching a string anyway: other types only come
        # from further function logic, which doesn't need to be part of the parser when
        # using a generator:
        age_text = yield regex(r"\d+") << whitespace
        age = int(age_text)
        if age > 20:
            # Parsing depends on previously parsed values
            note = yield regex(".+") >> success("Older than a score")
        else:
            note = yield regex(".+")

        return Person(name, age, note)

    return person_parser

person = person_parser().parse("Rob 21 once upon a time")

print(person)
