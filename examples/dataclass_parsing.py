from dataclasses import dataclass
from typing import Optional

from parsy import DataParser, dataparser, parse_field, regex, string, whitespace


@dataclass
class Person:
    name: str = parse_field(regex(r"\w+") << whitespace)
    age: int = parse_field(regex(r"\d+").map(int) << whitespace)
    note: str = parse_field(regex(".+"))


person_parser = dataparser(Person)
person = person_parser.parse("Rob 2000 how time flies")
print(person)
assert person == Person(name="Rob", age=2000, note="how time flies")


# Nesting dataclass parsers


@dataclass
class Id:
    id: str = parse_field(regex(r"[^\s]+") << whitespace.optional())
    from_year: Optional[int] = parse_field(
        regex("[0-9]+").map(int).desc("Numeric").optional() << whitespace.optional()
    )


@dataclass
class Name:
    name: str = parse_field(regex(r"[a-zA-Z]+") << whitespace.optional())
    abbreviated: Optional[bool] = parse_field(
        (string("T") | string("F")).map(lambda x: x == "T").optional() << whitespace.optional()
    )


@dataclass
class PersonDetail:
    id: Id = parse_field(dataparser(Id))
    forename: Name = parse_field(dataparser(Name))
    surname: Optional[Name] = parse_field(dataparser(Name).optional())


out_parser = dataparser(PersonDetail).many()

new_person = out_parser.parse("007 2023 Rob T John 123 2004 Bob")
print(new_person)

res = [
    PersonDetail(
        id=Id(id="007", from_year=2023),
        forename=Name(name="Rob", abbreviated=True),
        surname=Name(name="John", abbreviated=None),
    ),
    PersonDetail(id=Id(id="123", from_year=2004), forename=Name(name="Bob", abbreviated=None), surname=None),
]

# Dataclass parsing where not all fields have a parsy parser


@dataclass
class PersonWithRarity:
    name: str = parse_field(regex(r"\w+") << whitespace)
    age: int = parse_field(regex(r"\d+").map(int) << whitespace)
    note: str = parse_field(regex(".+"))
    rare: bool = False

    def __post_init__(self):
        if self.age > 70:
            self.rare = True


person_parser = dataparser(PersonWithRarity)
person = person_parser.parse("Rob 20 whippersnapper")
print(person)
assert person == PersonWithRarity(name="Rob", age=20, note="whippersnapper", rare=False)

person = person_parser.parse("Rob 2000 how time flies")
print(person)
assert person == PersonWithRarity(name="Rob", age=2000, note="how time flies", rare=True)


@dataclass
class PersonFromBase(DataParser):
    name: str = parse_field(regex(r"\w+") << whitespace)
    age: int = parse_field(regex(r"\d+").map(int) << whitespace)
    note: str = parse_field(regex(".+"))


print(PersonFromBase.parser().parse("Rob 2000 how time flies"))
