from dataclasses import dataclass
from typing import List

from parsy import dataclass_parser, parser_field, regex, string

text = """Sample text

A selection of students from Riverdale High and Hogwarts took part in a quiz. This is a record of their scores.

School = Riverdale High
Grade = 1
Student number, Name
0, Phoebe
1, Rachel

Student number, Score
0, 3
1, 7

Grade = 2
Student number, Name
0, Angela
1, Tristan
2, Aurora

Student number, Score
0, 6
1, 3
2, 9

School = Hogwarts
Grade = 1
Student number, Name
0, Ginny
1, Luna

Student number, Score
0, 8
1, 7

Grade = 2
Student number, Name
0, Harry
1, Hermione

Student number, Score
0, 5
1, 10

Grade = 3
Student number, Name
0, Fred
1, George

Student number, Score
0, 0
1, 0
"""


integer = regex(r"\d+").map(int)
any_text = regex(r"[^\n]+")


@dataclass
class Student:
    number: int = parser_field(integer << string(", "))
    name: str = parser_field(any_text << string("\n"))


@dataclass
class Score:
    number: int = parser_field(integer << string(", "))
    score: int = parser_field(integer << string("\n"))


@dataclass
class StudentWithScore:
    name: str
    number: int
    score: int


@dataclass
class Grade:
    grade: int = parser_field(string("Grade = ") >> integer << string("\n"))
    students: List[Student] = parser_field(
        string("Student number, Name\n") >> dataclass_parser(Student).many() << regex(r"\n*")
    )
    scores: List[Score] = parser_field(
        string("Student number, Score\n") >> dataclass_parser(Score).many() << regex(r"\n*")
    )

    @property
    def students_with_scores(self) -> List[StudentWithScore]:
        names = {st.number: st.name for st in self.students}
        return [StudentWithScore(names[score.number], score.number, score.score) for score in self.scores]


@dataclass
class School:
    name: str = parser_field(string("School = ") >> any_text << string("\n"))
    grades: List[Grade] = parser_field(dataclass_parser(Grade).many())


@dataclass
class File:
    header: str = parser_field(regex(r"[\s\S]*?(?=School =)"))
    schools: List[School] = parser_field(dataclass_parser(School).many())


if __name__ == "__main__":
    file = dataclass_parser(File).parse(text)
    print(file.schools)
