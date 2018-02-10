import itertools


def lines_from(filename, line):
    try:
        lines = lines_from.cache[filename]
    except KeyError:
        with open(filename) as fp:
            lines = lines_from.cache[filename] = list(fp)
    return itertools.islice(lines, line-1, None)

lines_from.cache = {}


def iter_dedent(lines):
    first_line = next(lines)
    indent = len(first_line) - len(first_line.lstrip())
    yield first_line[indent:]
    for line in lines:
        i = len(line) - len(line.lstrip())
        if i == len(line) or i > indent:
            yield line[indent:]
        else:
            break


def get_def_source(fn):
    code = fn.__code__
    lines = lines_from(code.co_filename, code.co_firstlineno)
    lines = iter_dedent(lines)
    lines = list(lines)
    source = ''.join(lines)
    return source


def get_def_ast(fn):
    source = get_def_source(fn)
    assert source.startswith('def ')
    module = ast.parse(source)
    r, = module.body
    return r
