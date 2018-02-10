import ast
import itertools
from lambdifier.lines import get_def_ast


def as_ast(fn):
    if isinstance(fn, ast.AST):
        return fn
    elif hasattr(fn, '__code__'):
        return get_def_ast(fn)
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
            return iter(iterable)
        except TypeError:
            # If method is not a generator function, then it has already
            # returned, so we simply return an empty iterable.
            return iter(())

    def generic_visit(self, node):
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        yield from self.visit(item)
            elif isinstance(value, ast.AST):
                yield from self.visit(value)


class LocalVars(Visitor):
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            yield node.id

    def visit_FunctionDef(self, node):
        # Don't recurse into function definitions
        pass

    def visit_arg(self, node):
        yield node.arg

    def __call__(self, node: ast.FunctionDef):
        # Call generic_visit() instead of visit() since we *do* want to recurse
        # into the first function.
        return tuple(sorted(set(self.generic_visit(node))))


def get_local_vars(node):
    node = as_ast(node)
    return LocalVars()(node)
