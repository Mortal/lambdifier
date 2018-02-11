import ast
import itertools
from lambdifier.lines import get_def_ast


def as_ast(fn):
    if isinstance(fn, ast.AST):
        return fn
    elif hasattr(fn, '__code__'):
        return get_def_ast(fn)
    elif isinstance(fn, str):
        mod = ast.parse(fn)
        node, = mod.body
        return node
    else:
        raise TypeError(type(fn).__name__)


class Visitor:
    def visit(self, node):
        if isinstance(node, list):
            return itertools.chain.from_iterable(map(self.visit, node))
        try:
            method = getattr(self, 'visit_' + node.__class__.__name__)
        except AttributeError:
            method = self.generic_visit
        iterable = method(node)
        try:
            iter(iterable)
        except TypeError:
            # If method is not a generator function, then it has already
            # returned, so we simply return an empty iterable.
            return ()
        return iterable

    def generic_visit(self, node):
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        yield from self.visit(item)
            elif isinstance(value, ast.AST):
                yield from self.visit(value)


def uniq(iterable):
    return tuple(sorted(set(iterable)))


class NameFinder(Visitor):
    def __init__(self):
        self.scopes = {}

    def visit(self, node):
        r = uniq(super().visit(node))
        self.scopes[id(node)] = r
        return r

    def visit_Name(self, node):
        raise NotImplementedError

    def visit_If(self, node):
        yield from self.visit(node.test)
        yield from self.visit(node.body)
        yield from self.visit(node.orelse)

    def visit_For(self, node):
        yield from self.visit(node.target)
        yield from self.visit(node.iter)
        yield from self.visit(node.body)
        yield from self.visit(node.orelse)

    def visit_arg(self, node):
        yield node.arg

    def visit_FunctionDef(self, node):
        # Only recurse into top-level function definition
        if node is self.node:
            yield from self.visit(node.args)
            yield from self.visit(node.body)

    def __call__(self, node: ast.FunctionDef):
        node = as_ast(node)
        self.node = node
        return uniq(self.visit(node))


class LocalVars(NameFinder):
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            yield node.id


class ReadVars(NameFinder):
    def visit_Name(self, node):
        if not isinstance(node.ctx, ast.Store):
            yield node.id


class ReadBeforeWrite(Visitor):
    def __init__(self):
        self.read_stack = [set()]
        self.write_stack = [set()]
        self.scopes = {}

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.write_stack[-1].add(node.id)
        else:
            for i in range(len(self.read_stack)-1, -1, -1):
                if node.id not in self.write_stack[i]:
                    self.read_stack[i].add(node.id)

    def visit_For(self, node):
        yield from self.visit(node.iter)
        self.read_stack.append(set())
        self.write_stack.append(set())
        yield from self.visit(node.target)
        yield from self.visit(node.body)
        yield from self.visit(node.orelse)
        self.scopes[id(node)] = self.read_stack.pop(), self.write_stack.pop()

    def visit_Assign(self, node):
        yield from self.visit(node.value)
        yield from self.visit(node.targets)

    def visit_AugAssign(self, node):
        yield from self.visit(node.value)
        yield from self.visit(node.target)

    def visit_If(self, node):
        yield from self.visit(node.test)
        self.read_stack.append(set())
        self.write_stack.append(set())
        yield from self.visit(node.body)
        self.scopes[id(node.body)] = (
            self.read_stack.pop(), self.write_stack.pop())
        self.read_stack.append(set())
        self.write_stack.append(set())
        yield from self.visit(node.orelse)
        self.scopes[id(node.orelse)] = (
            self.read_stack.pop(), self.write_stack.pop())

    def copy(self, node):
        r, w = self.scopes[id(node)]
        return r & w

    def visit_FunctionDef(self, node):
        # Only recurse into top-level function definition
        if node is self.node:
            yield from self.visit(node.args)
            yield from self.visit(node.body)

    def __call__(self, node: ast.FunctionDef):
        node = as_ast(node)
        self.node = node
        list(self.visit(node))


def get_local_vars(node):
    return LocalVars()(node)


class LoopFinder(Visitor):
    def visit_For(self, node):
        yield 'for'

    def visit_While(self, node):
        yield 'while'


def find_loops(node):
    return uniq(LoopFinder().visit(node))
