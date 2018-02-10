import unittest
from lambdifier import (
    get_def_source, get_def_ast, get_local_vars, LocalVars,
)
from lambdifier.lambdify import Lambdifier, foldl


class TestLines(unittest.TestCase):
    def test_simple(self):
        def f():
            return 42

        self.assertEqual(get_def_source(f), 'def f():\n    return 42\n')


class TestLocalVars(unittest.TestCase):
    def test_simple(self):
        def f():
            x = 1
            return y

        self.assertEqual(get_local_vars(f), ('x',))

    def test_nested(self):
        def f():
            x = 1

            def g():
                y = 1

        self.assertEqual(get_local_vars(f), ('x',))

    def test_param(self):
        def f(a, *b, c=0, **d):
            pass

        self.assertEqual(get_local_vars(f), ('a', 'b', 'c', 'd',))

    def test_scopes(self):
        def f(a):
            if a:
                b = 1
            else:
                c = 1

        l = LocalVars()
        locs = l(f)
        self.assertEqual(locs, ('a', 'b', 'c'))
        body = l.node.body
        if_, = body
        self.assertEqual(l.scopes[id(body)], ('b', 'c'))
        self.assertEqual(l.scopes[id(if_.body)], ('b',))
        self.assertEqual(l.scopes[id(if_.orelse)], ('c',))


class FoldTest(unittest.TestCase):
    def test_simple(self):
        foldl_ = eval(foldl)
        x = y = 0
        f = lambda x, y, i: (x+1, y+i)
        self.assertEqual(foldl_(f, (x, y), range(10)), (10, 45))


class LambdifierTest(unittest.TestCase):
    def test_arguments(self):
        def f(a, x=2, *b, c=0, **d):
            pass

        f = get_def_ast(f)
        self.assertEqual(''.join(Lambdifier().visit_arguments(f.args)),
                         ' a, x=2, *b, c=0, **d')

    def test_return(self):
        def f():
            return 42

        self.assertEqual(Lambdifier()(f),
                         'lambda: [_result for _result in [None] ' +
                         'for _result in [42]][0]')

    def test_assign(self):
        def f():
            x = 42
            return x

        self.assertEqual(Lambdifier()(f),
                         'lambda: [_result for _result in [None]' +
                         ' for x in [42]' +
                         ' for _result in [x]' +
                         '][0]')

    def test_if(self):
        def f(a):
            x = 0
            y = 0
            if a:
                x = 42
            else:
                y = 42
            return x

        source = Lambdifier()(f)
        self.assertEqual(source,
                         'lambda a: [_result for _result in [None]' +
                         ' for x in [0]' +
                         ' for y in [0]' +
                         ' for (x, y) in (' +
                         '[(x, y) for x in [42]]' +
                         ' if a else ' +
                         '[(x, y) for y in [42]]' +
                         ')' +
                         ' for _result in [x]' +
                         '][0]')
        l = eval(source)
        self.assertEqual(l(1), f(1))
        self.assertEqual(l(0), f(0))

    def test_for(self):
        def fib(n):
            a, b, c = 0, 1, 1
            for i in range(n):
                a, b, c = b, c, b + c
            return a

        self.assertEqual(fib(5), 5)
        self.assertEqual(fib(6), 8)
        source = Lambdifier()(fib)
        self.assertEqual(source,
                         'lambda n: [_result for _result in [None]' +
                         ' for _foldl in [%s]' % foldl +
                         ' for (a, b, c) in [(0, 1, 1)]' +
                         ' for (a, b, c) in [_foldl(lambda a, b, c, i:' +
                         ' [(a, b, c) for (a, b, c) in [(b, c, b + c)]][0],' +
                         ' (a, b, c), range(n))]' +
                         ' for _result in [a]' +
                         '][0]')
        l = eval(source)
        self.assertEqual(l(5), 5)
        self.assertEqual(l(6), 8)


def kmeans(x, K):
    r'''
    >>> from pprint import pprint
    >>> def kmeans_print(x, K):
    ...     dp, bt = kmeans(x, K)
    ...     print('\n'.join(' '.join('%g' % v for v in row[1:]) for row in dp[1:]))
    >>> kmeans_print([1, 2, 6, 7], 2)
    0 0
    0.5 0
    14 0.5
    26 1
    >>> kmeans_print([1, 2, 6, 7, 21], 3)
    0 0 0
    0.5 0 0
    14 0.5 0
    26 1 0.5
    257.2 26 1
    '''
    n, x = len(x), [None]+list(x)
    y = [None] * (n+1)
    dp = [[None]*(K+1) for _ in range(n+1)]
    bt = [[None]*(K+1) for _ in range(n+1)]
    for i in range(1, n+1):
        if i == 1:
            y[i] = x[i]
        else:
            y[i] = y[i-1] + x[i]
    for i in range(1, n+1):
        for k in range(1, K+1):
            if k >= i:
                dp[i][k] = 0
            elif k == 1:
                dp[i][k] = 0
                for j in range(1, i+1):
                    dp[i][k] = dp[i][k] + (x[j] - (1/i)*y[i])**2
            else:
                for j in range(1, i):
                    v = dp[j][k-1]
                    for h in range(j+1, i+1):
                        v = v + (x[h] - (1/(i-j))*(y[i]-y[j]))**2
                    if j == 1 or v < dp[i][k]:
                        dp[i][k] = v
                        bt[i][k] = j
    return (dp, bt)


class KmeansTest(unittest.TestCase):
    def test_kmeans(self):
        l = Lambdifier()(kmeans)
        print(l)
        kmeans2 = eval(l)
        self.assertEqual(kmeans([1, 2, 6, 7], 2),
                         kmeans2([1, 2, 6, 7], 2))


if __name__ == '__main__':
    unittest.main()
