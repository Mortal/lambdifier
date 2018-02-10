import unittest
from lambdifier import (
    get_def_source, get_local_vars,
)


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


if __name__ == '__main__':
    unittest.main()
