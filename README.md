Lambdifier
==========

Turn any* Python function into a oneliner!

Supported syntax:
- Assignment to local variable
- Slice assignment
- Attribute assignment
- For loop
- If statement
- Return statement at end of function

As of yet unsupported syntax:
- While loop
- def
- lambda
- raise

Out of scope syntax:
- break/continue
- return not at end of function
- for-else, while-else
- try-except
- try-finally

Example 1:

```python
from lambdifier import lambdify
source = '''
def fib(n):
    a, b, c = 0, 1, 1
    for i in range(n):
        a, b, c = b, c, b + c
    return a
'''
print(lambdify(source))
```

Output:

```python
lambda n: [_result
for (n,) in [(n,)]
for _result in [None]
for _foldl in [(lambda f, a, it: (lambda S=object(): lambda g=(lambda rec, f, a, it: [a if i is S else rec(rec, f, f(*a, i), it) for i in [next(it, S)]][0]): g(g, f, a, iter(it)))()())]
for (a, b, c) in [(0, 1, 1)]
for (a, b, c) in [_foldl(lambda a, b, c, i: [(a, b, c)
for (b, c) in [(b, c)]
for (a, b, c) in [(b, c, b + c)]][0],
(None, b, c), range(n))]
for _result in [a]][0]
```

Example 2:

```python
from lambdifier import lambdify
source = '''
def kmeans(x, K):
    n, x = len(x), [None]+list(x)
    dp = [[None]*(K+1) for _ in range(n+1)]
    for i in range(1, n+1):
        for k in range(1, K+1):
            if k >= i:
                dp[i][k] = 0
            elif k == 1:
                dp[i][k] = 0
                s = 0
                for j in range(1, i+1):
                    s = s + x[j]
                for j in range(1, i+1):
                    dp[i][k] = dp[i][k] + (x[j] - (1/i)*s)**2
            else:
                for j in range(1, i):
                    v = dp[j][k-1]
                    s = 0
                    for h in range(j+1, i+1):
                        s = s + x[h]
                    for h in range(j+1, i+1):
                        v = v + (x[h] - (1/(i-j))*s)**2
                    if j == 1 or v < dp[i][k]:
                        dp[i][k] = v
    return dp
'''
print(lambdify(source))
```

Output:
```python
lambda x, K: [_result
for (x, K) in [(x, K)]
for _result in [None]
for _foldl in [(lambda f, a, it: (lambda S=object(): lambda g=(lambda rec, f, a, it: [a if i is S else rec(rec, f, f(*a, i), it) for i in [next(it, S)]][0]): g(g, f, a, iter(it)))()())]
for (n, x) in [(len(x), [None] + list(x))]
for dp in [[[None] * (K + 1) for _ in range(n + 1)]]
for (h, j, k, s, v) in [_foldl(lambda h, j, k, s, v, i: [(h, j, k, s, v)
for (h, j, s, v) in [_foldl(lambda h, j, s, v, k: [(h, j, s, v)
for (h, j, s, v) in ([(h, j, s, v)
for _t0 in [0]
for _ in [(dp[i]).__setitem__(k, _t0)]]
if k >= i else
[(h, j, s, v)
for (h, j, s, v) in ([(h, j, s, v)
for _t0 in [0]
for _ in [(dp[i]).__setitem__(k, _t0)]
for s in [0]
for (s,) in [_foldl(lambda s, j: [(s,)
for (s) in [(s)]
for s in [s + x[j]]][0],
(s,), range(1, i + 1))]
for _ in [_foldl(lambda j: [()
for _t0 in [dp[i][k] + (x[j] - 1 / i * s) ** 2]
for _ in [(dp[i]).__setitem__(k, _t0)]][0],
(), range(1, i + 1))]]
if k == 1 else
[(h, j, s, v)
for (h, s, v) in [_foldl(lambda h, s, v, j: [(h, s, v)
for v in [dp[j][k - 1]]
for s in [0]
for (s,) in [_foldl(lambda s, h: [(s,)
for (s) in [(s)]
for s in [s + x[h]]][0],
(s,), range(j + 1, i + 1))]
for (v,) in [_foldl(lambda v, h: [(v,)
for (v) in [(v)]
for v in [v + (x[h] - 1 / (i - j) * s) ** 2]][0],
(v,), range(j + 1, i + 1))]
for _ in ([0
for _t0 in [v]
for _ in [(dp[i]).__setitem__(k, _t0)]]
if j == 1 or v < dp[i][k] else
[0])][0],
(None, None, None), range(1, i))]])])][0],
(None, None, None, None), range(1, K + 1))]][0],
(None, None, None, None, None), range(1, n + 1))]
for _result in [dp]][0]
```


CPython details
---------------

In Python, an UnboundLocalError is raised if a local variable is read before it is written.
A local variable is a name that appears as an assignment target in code.
Thus, the following code is illegal:

```python
x = 0

def f():
    x = x + 1  # UnboundLocalError

f()
```

In `lambdifier`, this issue is routed around by passing environments as parameters,
conceptually by changing the above example to:

```python
x = 0

def f(x):
    x = x + 1
    return x

x = f(x)
```

Python introduces a local variable scope in each list comprehension,
evaluating the first comprehension in the caller's scope
and subsequent comprehensions in the callee.
In the following example, `a` is evaluated outside the list comprehension's implicit function,
and `b` is evaluated inside; the local variables (assignment targets) are `x` and `y`:

```python
[x+y for x in a for y in b]
```

Thus, the expression `a` may mention variables `x` and `y` in the enclosing scope,
but the expression `b` may not. The following code is fine:

```python
y = 1
print([x+y for x in [y] for y in [0]])  # prints [1]
```

On the other hand, the following code raises `UnboundLocalError`:

```python
y = 1
print([x+y for x in [0] for y in [y]])  # UnboundLocalError
```

Thus, when passing environments around,
this must be done in the outermost comprehension.
