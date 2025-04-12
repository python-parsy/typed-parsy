# from parsy import digit, generate, match_char, regex, string, success


# def lexer(code):
#     whitespace = regex(r"\s*")
#     integer = digit.at_least(1).concat().map(int)
#     float_ = (digit.many() + string(".").result(["."]) + digit.many()).concat().map(float)
#     parser = whitespace >> ((float_ | integer | regex(r"[()*/+-]")) << whitespace).many()
#     return parser.parse(code)


# def eval_tokens(tokens):
#     # This function parses and evaluates at the same time.

#     lparen = match_char("(")
#     rparen = match_char(")")

#     @generate
#     def additive():
#         res = yield multiplicative
#         sign = match_char("+") | match_char("-")
#         while True:
#             operation = yield sign | success("")
#             if not operation:
#                 break
#             operand = yield multiplicative
#             if operation == "+":
#                 res += operand
#             elif operation == "-":
#                 res -= operand
#         return res

#     @generate
#     def multiplicative():
#         res = yield simple
#         op = match_char("*") | match_char("/")
#         while True:
#             operation = yield op | success("")
#             if not operation:
#                 break
#             operand = yield simple
#             if operation == "*":
#                 res *= operand
#             elif operation == "/":
#                 res /= operand
#         return res

#     @generate
#     def number():
#         sign = yield match_char("+") | match_char("-") | success("+")
#         value = yield test_item(lambda x: isinstance(x, (int, float)), "number")
#         return value if sign == "+" else -value

#     expr = additive
#     simple = (lparen >> expr << rparen) | number

#     return expr.parse(tokens)


# def simple_eval(expr):
#     return eval_tokens(lexer(expr))


# import pytest  # noqa  isort:skip

# test_item = pytest.mark.skip(test_item)  # This is not a test


# if __name__ == "__main__":
#     print(simple_eval(input()))
