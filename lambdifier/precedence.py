import ast
import contextlib


PRECEDENCE = [
    [ast.Lambda],
    [ast.IfExp],
    [ast.Or],
    [ast.And],
    [ast.Not],
    [ast.In, ast.NotIn, ast.Is, ast.IsNot, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
     ast.NotEq, ast.Eq],
    [ast.BitOr],
    [ast.BitXor],
    [ast.BitAnd],
    [ast.LShift, ast.RShift],
    [ast.Add, ast.Sub],
    [ast.Mult, ast.MatMult, ast.Div, ast.FloorDiv, ast.Mod],
    [ast.UAdd, ast.USub, ast.Invert],
    [ast.Pow],
    [ast.Await],
    [ast.Subscript, ast.Call, ast.Attribute],
    [ast.Tuple, ast.List, ast.Dict, ast.Set],
]


def precedence(op):
    for i in range(len(PRECEDENCE)):
        if op in PRECEDENCE[i]:
            return i


class AutoParens:
    def __init__(self):
        self.precedence = [-1]
        self.p_level = 0

    @contextlib.contextmanager
    def __call__(self, node, op, left, right):
        # From fstrings
        prec = precedence(type(op))
        if self.precedence[-1] > prec:
            self.precedence.append(-1)
            self.p_level += 1
            yield '(', ')'
            self.p_level -= 1
            self.precedence.pop()
        else:
            self.precedence.append(prec)
            yield '', ''
            self.precedence.pop()
