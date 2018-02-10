import ast


class Visitor:
    def visit(self, node):
        try:
            method = getattr(self, 'visit_' + node.__class__.__name__)
        except AttributeError:
            method = self.generic_visit
        return (yield from method(node))

    def generic_visit(self, node):
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        yield from self.visit(item)
            elif isinstance(value, ast.AST):
                return (yield from self.visit(value))


class LocalVars(Visitor):
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            yield node.id

    def __call__(self, node):
        return tuple(sorted(set(self.visit(node))))
