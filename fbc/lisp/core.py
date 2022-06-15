import inspect
from collections.abc import Iterable
from typing import List, Union, Any

atom_types = {int, str, bool, float}


def sexp_like(obj):
    """
    Checks if supplied object is 'sexp_like'. I.e. checks if a `to_sexp` function exists.
    :param obj: obj
    :return: if `obj` is `sexp_like`
    """
    return hasattr(obj, 'to_sexp')


def is_enum_sexp(sexp, enums):
    """
    Checks if sexp is an enum symbol. An enum symbol must fulfill following conditions:
      - sexp must be a 'symbol' sexp
      - symbol name must be in 'enums'
    """
    return isinstance(sexp, tuple) and len(sexp) == 3 and sexp[0] == 'symbol' and sexp[1] in enums


def sexp_type(sexp):
    """
    Returns the type of an sexp based on the following rules:
     - if sexp is a tuple, the first element (sexp operation) is returned
     - if sexp is an atom, the data type of the atom is returned
     - if sexp is a list, 'list' is returned
    :param sexp: sexp
    :return: sexp_type
    """
    if isinstance(sexp, tuple):
        return sexp[0]
    elif isinstance(sexp, list):
        return 'list'
    elif type(sexp) in [int, float]:
        return 'number'
    elif type(sexp) == str:
        return 'string'
    elif type(sexp) == bool:
        return 'boolean'
    else:
        raise ValueError(f"could not determine sexp type from {sexp}")


def is_atom(sexp):
    """
    Checks if sexp is an atom

    :param sexp: sexp
    :return: If sexp is an atom
    """
    return type(sexp) in atom_types


def infix_to_sexp(tokens):
    """
    Converts a list of tokens from infix notation to sexp notation.

    E.g. [1, '+', 2, '+', 3] -> ('+', ('+', 1, 2), 3)

    :param tokens: list of tokens. Must be of unequal length. Every token on even position is considered as operand.
                   Every token on uneven position is considered as operator.
    :return: sexp representation
    """
    if len(tokens) % 2 != 1:
        raise ValueError("infix list must contain an uneven amount of items")

    ops = [tokens[(2*i)+1] for i in range(len(tokens) // 2)]
    operands = [tokens[2*i] for i in range((len(tokens) // 2) + 1)]

    if len(ops) != len(operands)-1 or len(ops) < 1:
        raise ValueError(f"inconsistent operators or operands. ops: ${ops}, operands: {operands}")

    sexp = (ops[0], operands[0], operands[1])

    for i in range(1, len(ops)):
        if ops[i] == sexp[0]:
            sexp = sexp + (operands[i+1], )
        else:
            sexp = (ops[i], sexp, operands[i+1])

    return sexp


class Lisp:
    """
    Superclass for Lisp evaluation.

    == BASIC USAGE ==
    For basic usage define a subclass of Lisp and mark functions with `Lisp.handle` decorators

    class PlusLisp(Lisp):
        @Lisp.handle('+')
        def handle_plus(op, lop, rop):
            return lop + rop

    PlusLisp.eval(('+', 1, 2)) --> 3
    PlusLisp.eval(('+', 1, ('+', 2, 3))) --> 6

    The first argument of an sexp handle is the operator itself. This argument can be used to distinguish between
    operators in case a list of operators was defined.

    class PlusMinusLisp(Lisp):
        @Lisp.handle(['+', '-'])
        def handle_plus(op, lop, rop):
            if op == '+':
                return lop + rop
            elif op == '-':
                return lop - rop
            else:
                raise ValueError()

    == Condition handles ==
    Instead of an explicit operator, it is also possible to supply a function. The supplied object does not necessarily
    need to follow standard sexp patterns.

    class ProjectFirstLisp(Lisp):
        @Lisp.handle(lambda sexp: len(sexp) == 3)
        def project(arg1, arg2, arg3):
            return arg1

    ProjectFirstLisp.eval((1, 2, 3)) --> 1

    == Lisp.NOOP ==
    If a handle returns `Lisp.NOOP` the return value will be the supplied sexp itself

    class PlusLisp(Lisp):
        @Lisp.handle('+')
        def handle_small_plus(op, lop, rop):
            if abs(lop+rop) > 9:
                return Lisp.NOOP
            else:
                return lop + rop

        PlusLisp.eval(('+', 1, 2)) --> 3  # evaluates normally
        PlusLisp.eval(('+', 10, 10)) --> ('+', 10, 10)  # returns sexp itself because result is greater than 9

    == Leafs ==
    To prevent recursive evaluation for certain attributes, define leafs as a collection of indices

    class IfLisp(Lisp):
        @Lisp.handle('if', leafs=[1, 2])  # defines `true_exp` and `false_exp` as leafs
        def handle_if(op, bool_val, true_exp, false_exp):
            # `bool_val` is evaluated here, since argument 0 is not a leaf
            # `true_exp` and `false_exp` are not evaluated and are supplied as defined in the sexp
            if bool_val:
                return true_exp
            else:
                return false_exp

        @Lisp.handle('>')
        def handle_gt(op, lop, rop):
            return lop > rop

    IfLisp.eval(('if', ('>', 2, 1), ('exp1', 1, 2), ('exp2', 'a', 'b')) --> ('exp1', 1, 2)

    Note that argument 0 `('>', 2, 1)` is evaluated as `True` while arguments 1 and 2 are not evaluated because
    they were defined as leafs.
    To define all arguments as leafs, use `Lisp.ALL`.
    """

    # Marks that the result of an sexp should be the sexp itself
    NOOP = object()

    # Handle register
    handle_reg = []

    class _Wildcard:
        # instances of `Wildcard` will always return `True` for `x in wildcard` expressions
        def __contains__(self, item):
            return True

    ALL = _Wildcard()

    def __init__(self, scope=None):
        if scope is None:
            # by default use an empty `DictScope`
            scope = DictScope({})

        self.scope = scope
        self.sexp_handles = {}
        self.sexp_cond_handles = []
        self._register_decorator_handles()

    @classmethod
    def handle(cls, ops, default=None, leafs=None):
        """
        Decorator to mark a function as sexp handle. An sexp handle can be used to evaluate an sexp of a certain type.

        :param ops: operation(s) to be handled.
        :param default: default return value (replacing `None`)
        :param leafs: Determines sexp 'leafs'. (See 'Leafs' in `Lisp` class docstring above)

        :return: function decorator
        """
        if leafs is None:
            leafs = set()

        def decorator(fun):
            Lisp.handle_reg.append((ops, fun, default, leafs))
            return fun

        return decorator

    @classmethod
    def eval(cls, sexp, *args, **kwargs):
        """
        Creates an instance of the Lisp using `args` and `kwargs` and applies it on `sexp`

        :param sexp: sexp to be evaluated
        :param args: argument for Lisp instance
        :param kwargs: kwargs for Lisp instance
        :return: evaluated sexp
        """
        return cls(*args, **kwargs).eval_step(sexp)

    def _register_decorator_handles(self):
        """
        Registers all handles that were defined in the respective Lisp subclass
        """
        for _, mem in inspect.getmembers(self):
            if not hasattr(mem, '__func__'):
                continue

            bound_func = mem
            mem_func = bound_func.__func__

            handles = [(op, bound_func, default, leafs)
                       for op, reg_fun, default, leafs in Lisp.handle_reg if reg_fun == mem_func]

            for op, bound_func, default, leafs in handles:
                self.register_handle(op, bound_func, default, leafs)

    def register_handle(self, ops, fun, default=None, leafs=None):
        """
        Registers an sexp handle for a certain (list) of operations.

        :param ops: operation(s) to be handled by the supplied sexp handle
        :param fun: sexp handle
        :param default: default return value (replacing `None`)
        :param leafs: Determines sexp 'leafs'. (See 'Leafs' in `Lisp` class docstring above)
        """
        if leafs is None:
            leafs = []

        if isinstance(ops, dict):
            ops = list(ops.keys())
        elif isinstance(ops, list):
            pass
        elif isinstance(ops, str):
            ops = [ops]
        elif isinstance(ops, Iterable):
            ops = list(ops)
        else:
            ops = [ops]

        for op in ops:
            if callable(op):
                self.sexp_cond_handles.append((op, fun, default, leafs))
            else:
                if op in self.sexp_handles:
                    raise ValueError(f"Cannot register operator twice: {op}")

                self.sexp_handles[op] = (fun, default, leafs)

    def eval_step(self, sexp):
        """
        Recursive function to evaluate given `sexp`
        :param sexp: sexp to evaluate
        :return: result
        """
        typ = sexp_type(sexp)

        # lookup handle for explicit sexp type/ operation
        handle_def = self.sexp_handles.get(typ)

        if handle_def is None:
            # if no explicit handle was found, try to apply any condition handles
            cond_handles = [(__handle, default, leafs)
                            for cond, __handle, default, leafs in self.sexp_cond_handles if cond(sexp)]
            if len(cond_handles) == 0:
                op_handle = None
                default = None
                leafs = set()
            else:
                # select first applicable handle
                op_handle, default, leafs = cond_handles[0]
        else:
            op_handle, default, leafs = handle_def

        if isinstance(sexp, tuple):
            # apply `eval_step` recursively for all non leaf arguments
            eval_args = tuple([arg if idx in leafs else self.eval_step(arg) for idx, arg in enumerate(sexp[1:])])

            if op_handle is None:
                # if no op_handle was defined, return the sexp unaltered
                res = (sexp[0], ) + eval_args
            else:
                # apply op handle on evaluated arguments
                res = op_handle(*(sexp[0], ) + eval_args)

            # if Lisp.NOOP was returned, return the arguments unaltered
            if res == Lisp.NOOP:
                res = (sexp[0], ) + eval_args
        elif is_atom(sexp):
            if op_handle is None:
                res = sexp
            else:
                res = op_handle(sexp)

            if res == Lisp.NOOP:
                res = sexp
        elif isinstance(sexp, list):
            res = [self.eval_step(it) for it in sexp]
        else:
            raise ValueError(f"unexpected type in sexp evaluation: {type(sexp)}")

        if res is None:
            res = default

        if isinstance(res, tuple) or isinstance(res, list) or is_atom(res):
            return res
        elif sexp_like(res):
            return res.to_sexp()
        else:
            return res


class Scope:
    """
    Scope for variable lookup in hierarchical scopes. The main uses are (1) registering objects and (2) lookup
    objects.
    Both registering and lookup can be done either by dot notation (like 'foo.bar.baz') or list notation
    (like ['foo', 'bar', 'baz']). All lookups/registers except for the last are then expected to be scopes. The
    final object can then be any arbitrary object. (i.e. 'foo.bar' -> lookup 'foo' -> expect it to be a scope
    -> lookup 'bar' -> can be any object)
    """

    def _register(self, ident: str, obj: Any) -> None:
        """
        Define how an object is registered in a plain/non-hierarchical way
        :param ident: plain identifier
        :param obj: obj
        """
        raise NotImplemented()

    def register(self, idents: Union[List[str], str], obj: Any) -> None:
        """
        Register an object using a fully qualified identifier. The identifier can can be supplied by dot notation
        (like 'foo.bar.baz') or as a list  (like ['foo', 'bar', 'baz']). The lookups will then be applied
        recursively. I.e. all lookups before the last are expected to return scopes.
        The last identifier will be used to identify the object in the respective parent scope.

        :param idents: fully qualified identifier in dot notation or as list
        :param obj: object to be registered
        """
        if isinstance(idents, str):
            idents = idents.split(".")

        if len(idents) == 0:
            raise ValueError('ids is empty')
        elif len(idents) == 1:
            self._register(idents[0], obj)
        else:
            sub_scope = self._lookup(idents[0])
            sub_scope.register(idents[1:], obj)

    def _lookup(self, ident: str) -> Any:
        """
        Define how an object is beeing looked up in a plain/non-hierarchical way
        :param ident: plain identifier
        :return obj
        """
        raise NotImplemented()

    def lookup(self, idents: Union[List[str], str]) -> Any:
        """
        Lookup an object using a fully qualified identifier. The identifier can can be supplied by dot notation
        (like 'foo.bar.baz') or as a list  (like ['foo', 'bar', 'baz']). The lookups will then be applied
        recursively. I.e. all lookups before the last are expected to return scopes.
        The last identifier will be used to look up the object in the respective parent scope.

        :param idents: fully qualified identifier in dot notation or as list
        :return obj
        """
        if isinstance(idents, str):
            idents = idents.split('.')

        if len(idents) == 0:
            raise ValueError('ids is empty')
        elif len(idents) == 1:
            return self._lookup(idents[0])
        else:
            sub_scope = self._lookup(idents[0])
            return sub_scope.lookup(idents[1:])

    def __getitem__(self, item):
        return self.lookup(item)

    def __contains__(self, item):
        raise NotImplemented()


class DictScope(Scope):
    """
    Simple dict to register the scopes variables
    """
    def __init__(self, d=None):
        self.d = {}

        if d is not None:
            for k, v in d.items():
                self.register(k, v)

    def _register(self, ident: str, obj: Any) -> None:
        self.d[ident] = obj

    def _lookup(self, ident: str) -> Any:
        return self.d[ident]

    def __contains__(self, item):
        return item in self.d


class Macro:
    def __init__(self, ins, handle):
        self.ins = ins
        self.handle = handle

    def to_sexp(self):
        return 'macro', self.ins, self.handle
