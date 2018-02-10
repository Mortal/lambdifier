import re
import ast
import itertools
from lambdifier.visitor import (
    LocalVars, ReadVars, as_ast, find_loops, ReadBeforeWrite)
from lambdifier.precedence import AutoParens


foldl = (
    '(lambda f, a, it: ' +
    '(lambda S=object(): ' +
    'lambda g=(lambda rec, f, a, it: ' +
    '[a if i is S else rec(rec, f, f(*a, i), it) ' +
    'for i in [next(it, S)]][0]): g(g, f, a, iter(it)))()())')


class Visitor:
    def visit(self, node):
        if isinstance(node, list):
            yield from itertools.chain.from_iterable(map(self.visit, node))
        else:
            method_name = 'visit_' + node.__class__.__name__
            method = getattr(self, method_name)
            try:
                yield from method(node)
            except Exception:
                print('In', method_name)
                raise


class Lambdifier(Visitor):
    def __call__(self, node):
        self.auto_parens = AutoParens()
        self.copy_vars = ReadBeforeWrite()

        node = as_ast(node)
        self.node = node
        self.copy_vars(node)
        lv = LocalVars()
        rv = ReadVars()
        write = lv(self.node)
        read = ' '.join(rv(self.node))
        self.scopes = lv.scopes
        self.return_var = '_result'
        self.target_var = '_t'
        self.unused_var = '_'
        # User code may not write to our result variable
        assert self.return_var not in set(write)
        # User code may not read our temporaries
        temp_pattern = r'\b_(t\d*)?\b'
        assert not re.search(temp_pattern, read)
        return ''.join(self.toplevel(node))

    def toplevel(self, node):
        yield 'lambda'
        yield from self.visit(node.args)
        yield ': [{r}'.format(r=self.return_var)
        # Copy parameters so they become local variables to the loop comprehension
        par = ', '.join(self.arg_names(node.args))
        if par:
            if ', ' not in par:
                par += ','
            yield ' for ({par}) in [({par})]'.format(par=par)
        yield ' for {r} in [None]'.format(r=self.return_var)
        loops = find_loops(node)
        if 'for' in loops:
            yield ' for _foldl in [%s]' % foldl
        yield from self.visit(node.body)
        yield '][0]'

    def visit_Return(self, node):
        yield ' for %s in [' % self.return_var
        if node.value:
            yield from self.visit(node.value)
        else:
            yield 'None'
        yield ']'

    def primitive_assign(self, target_name: ast.Name, node):
        yield ' for %s in [' % target_name
        yield from self.visit(node)
        yield ']'

    def visit_Expr(self, expr):
        if isinstance(expr.value, ast.Str):
            return
        yield from self.primitive_assign(self.unused_var, expr.value)

    def assign_single(self, target, expr):
        self.assign_temp = []
        yield ' for '
        method = getattr(self, 'target_' + target.__class__.__name__)
        yield from method(target)
        yield ' in ['
        yield from self.visit(expr)
        yield ']'
        for f in self.assign_temp:
            yield from f
        del self.assign_temp

    def target_Name(self, target):
        yield target.id

    def target_Attribute(self, target):
        n = len(self.assign_temp)
        tmp = '_t%s' % n

        def f():
            yield ' for %s in [setattr(' % self.unused_var
            yield from self.visit(target.value)
            yield ', %r, %s)]' % (target.attr, tmp)

        self.assign_temp.append(f())
        yield tmp

    def target_Subscript(self, target):
        n = len(self.assign_temp)
        tmp = '_t%s' % n

        def f():
            yield ' for %s in [(' % self.unused_var
            yield from self.visit(target.value)
            yield ').__setitem__('
            yield from self.visit(target.slice)
            yield ', %s)]' % tmp

        self.assign_temp.append(f())
        yield tmp

    def target_Tuple(self, target):
        yield '('
        for i, e in enumerate(target.elts):
            if i:
                yield ', '
            method = getattr(self, 'target_' + e.__class__.__name__)
            yield from method(e)
        yield ')'

    def visit_Assign(self, node):
        if len(node.targets) == 1:
            yield from self.assign_single(node.targets[0], node.value)
            targets = ()
        elif isinstance(node.targets[0], ast.Name):
            # Common case (assign expr to single local variable)
            tmp_target = node.targets[0].id
            targets = node.targets[1:]
            yield from self.primitive_assign(tmp_target, node.value)
        else:
            # Assign to temporary
            tmp_target = self.target_var
            targets = node.targets
            yield from self.primitive_assign(tmp_target, node.value)
        for target in targets:
            yield from self.assign_single(target, ast.Name(tmp_target, None))

    def format_args(self, args, defaults):
        def f_arg_default(default):
            def f(arg):
                yield arg.arg + '='
                yield from self.visit(default)

            return f

        x = ([lambda arg: [arg.arg]] * (len(args) - len(defaults)) +
             [f_arg_default(v) for v in defaults])
        return [f(arg) for arg, f in zip(args, x)]

    def arg_names(self, node):
        for arg in node.args + [node.vararg] + node.kwonlyargs + [node.kwarg]:
            if arg is not None:
                yield arg.arg

    def visit_arguments(self, node):
        args = self.format_args(node.args, node.defaults)
        if node.vararg:
            args.append(['*' + node.vararg.arg])
        args.extend(self.format_args(node.kwonlyargs, node.kw_defaults))
        if node.kwarg:
            args.append(['**' + node.kwarg.arg])
        sep = ' '
        for f in args:
            yield sep
            yield from f
            sep = ', '

    def visit_AugAssign(self, node):
        # From fstrings
        ops = {
            ast.Mod: '%',
            ast.Sub: '-',
            ast.Add: '+',
            ast.Mult: '*',
            ast.Pow: '**',
            ast.Div: '/',
            ast.FloorDiv: '//',
        }
        # Rewrite into Assign and BinOp,
        # even though this is not always valid
        return self.visit(ast.Assign(
            [node.target], ast.BinOp(node.target, node.op, node.value)))

    def visit_If(self, node):
        locs = ', '.join(self.scopes[id(node)])
        result_vars = ('(%s)' % locs) if locs else self.unused_var
        result_vals = ('(%s)' % locs) if locs else '0'
        yield ' for %s in (' % result_vars
        yield '[%s' % result_vals
        v = self.copy_vars.copy(node.body)
        if v:
            v = ', '.join(sorted(v))
            yield ' for (%s) in [(%s)]' % (v, v)
        yield from self.visit(node.body)
        yield '] if '
        yield from self.visit(node.test)
        yield ' else [%s' % result_vals
        v = self.copy_vars.copy(node.orelse)
        if v:
            v = ', '.join(sorted(v))
            yield ' for (%s) in [(%s)]' % (v, v)
        yield from self.visit(node.orelse)
        yield '])'

    def visit_For(self, node):
        self.assign_temp = []
        target_name = '_i'
        if isinstance(node.target, ast.Name):
            target_name = node.target.id
        try:
            var_list = list(self.scopes[id(node.body)])
        except KeyError:
            print("No locals in for loop?")
            raise
        copy = self.copy_vars.copy(node)
        result_vars = ', '.join(var_list)
        init_vars = ', '.join(v if v in copy else 'None' for v in var_list)
        lambda_vars = ', '.join(var_list + [target_name])
        unpack = ('(%s,)' % result_vars if len(var_list) == 1 else
                  self.unused_var if len(var_list) == 0 else
                  '(%s)' % result_vars)
        pack = ('(%s,)' % result_vars if len(var_list) == 1 else
                '(%s)' % result_vars)
        init = ('(%s,)' % init_vars if len(var_list) == 1 else
                '(%s)' % init_vars)
        yield ' for {res} in [_foldl(lambda {par}: [{ret}'.format(
            res=unpack,
            par=lambda_vars,
            ret=pack)
        if copy:
            v = ', '.join(sorted(copy))
            yield ' for (%s) in [(%s)]' % (v, v)
        yield from self.visit(node.body)
        yield '][0], %s, ' % init
        yield from self.visit(node.iter)
        yield ')]'

    def visit_Pass(self, node):
        yield ' for %s in ["pass"]' % self.unused_var

    def commasep_visit(self, xs):
        for i, x in enumerate(xs):
            if i:
                yield ', '
            yield from self.visit(x)

    def visit_Call(self, node):
        # From fstrings
        yield from self.visit(node.func)
        yield '('
        yield from self.commasep_visit(node.args)
        for j, kw in enumerate(node.keywords):
            k = kw.arg
            v = kw.value
            if j or node.args:
                yield ','
            if k is None:
                yield '**'
            else:
                yield k + '='
            yield from self.visit(v)
        yield ')'

    def visit_Name(self, node):
        yield node.id

    def visit_Num(self, node):
        yield str(node.n)

    def visit_Str(self, node):
        yield repr(node.s)

    def visit_NameConstant(self, node):
        yield repr(node.value)

    def visit_Tuple(self, node):
        # From fstrings
        if len(node.elts) > 0:
            yield '('
            yield from self.visit(node.elts[0])
            for e in node.elts[1:]:
                yield ', '
                yield from self.visit(e)
            if len(node.elts) == 1:
                yield ','
            yield ')'
        else:
            yield '()'

    def visit_List(self, node):
        # From fstrings
        yield '['
        yield from self.commasep_visit(node.elts)
        yield ']'

    def visit_ListComp(self, node):
        yield '['
        yield from self.visit(node.elt)
        yield from self.visit(node.generators)
        yield ']'

    def visit_comprehension(self, node):
        yield ' async for ' if node.is_async else ' for '
        yield from self.visit(node.target)
        yield ' in '
        yield from self.visit(node.iter)
        for e in node.ifs:
            yield ' if '
            yield from self.visit(e)

    def visit_Dict(self, node):
        # From fstrings
        yield '{'
        for k, v in zip(node.keys, node.values):
            yield from self.visit(k)
            yield ': '
            yield from self.visit(v)
            yield ','
        yield '}'

    def visit_BinOp(self, node):
        # From fstrings
        ops = {
            ast.Mod: '%',
            ast.Sub: '-',
            ast.Add: '+',
            ast.Mult: '*',
            ast.Pow: '**',
            ast.Div: '/',
            ast.FloorDiv: '//',
        }
        with self.auto_parens(node, node.op, node.left, node.right) as (l, r):
            yield l
            yield from self.visit(node.left)
            yield ' %s ' % (ops.get(type(node.op), str(node.op)),)
            yield from self.visit(node.right)
            yield r

    def visit_BoolOp(self, node):
        ops = {
            ast.And: ' and ',
            ast.Or: ' or ',
        }
        with self.auto_parens(node, node.op, node.values[0], node.values[-1]) as (l, r):
            yield l
            for i, v in enumerate(node.values):
                if i:
                    yield ops[type(node.op)]
                yield from self.visit(v)
            yield r

    def visit_Compare(self, node):
        # From fstrings
        yield from self.visit(node.left)
        ops = {
            ast.Lt: '<',
            ast.Gt: '>',
            ast.LtE: '<=',
            ast.GtE: '>=',
            ast.Eq: '==',
            ast.NotEq: '!=',
            ast.In: ' in ',
            ast.Is: ' is ',
            ast.IsNot: ' is not ',
        }
        for op, right in zip(node.ops, node.comparators):
            yield ' %s ' % (ops.get(type(op), '?'),)
            yield from self.visit(right)

    def visit_Subscript(self, node):
        yield from self.visit(node.value)
        yield '['
        yield from self.visit(node.slice)
        yield ']'

    def visit_Index(self, node):
        yield from self.visit(node.value)


def lambdify(node):
    return Lambdifier()(node)
