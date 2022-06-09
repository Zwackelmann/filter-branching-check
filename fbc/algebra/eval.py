from sympy import Symbol, Integer, Float
from sympy.logic.boolalg import Boolean
from fbc.lisp.core import Lisp, is_atom
from fbc.algebra.core import AlgOps


class AlgInterpreter(Lisp):
    """
    Interprets an sexp as a sympy expression.
    """
    @Lisp.handle({**AlgOps.relation, **AlgOps.binary_arith, **AlgOps.unary_arith, **AlgOps.binary_logic,
                  **AlgOps.unary_logic})
    def handle_ops(self, op, *args):
        for op_class in [AlgOps.relation, AlgOps.binary_arith, AlgOps.unary_arith, AlgOps.binary_logic,
                         AlgOps.unary_logic]:
            if op in op_class:
                return op_class[op](*args)

        raise ValueError(f'Could not evaluate {op}')

    @Lisp.handle('symbol', leafs=Lisp.ALL)
    def handle_symbol(self, _, sym, typ):
        if isinstance(sym, Symbol):
            return sym
        else:
            if typ == 'string':
                return Symbol(sym, integer=True, finite=True)
            elif typ == 'number':
                return Symbol(sym, real=True, finite=True)
            elif typ == 'boolean':
                return Symbol(sym, bool=True)
            else:
                return Symbol(sym)

    @Lisp.handle(is_atom)
    def handle_atoms(self, a):
        if type(a) == int:
            return Integer(a)
        elif type(a) == float:
            return Float(a)
        elif type(a) == bool:
            return Boolean(a)
        elif type(a) == str:
            return Symbol(a, integer=True, finite=True)
        else:
            raise ValueError(f"Cannot convert atom to sympy symbol: {a}")
