from sympy import Symbol, Integer, Float, Eq, Or, Ne
from fbc.lisp.core import Lisp, is_atom
from fbc.algebra.core import AlgOps, Enum, EnumIn


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

    @Lisp.handle('in', leafs=Lisp.ALL)
    def handle_in(self, _, sym_sexp, lset):
        if isinstance(sym_sexp, Enum):
            enum = sym_sexp
            # return Or(*[Eq(enum.var, enum.member_vars[lit]) for lit in lset])
            return EnumIn(enum.var, lset)
        else:
            if isinstance(sym_sexp, tuple):
                sym = self.handle_symbol(*sym_sexp)
            else:
                sym = self.handle_atoms(sym_sexp)

            lset = {self.eval_step(s) for s in lset}
            return Or(*[Eq(sym, lit) for lit in lset])

    @Lisp.handle('nin', leafs=Lisp.ALL)
    def handle_nin(self, _, sym_sexp, lset):
        if isinstance(sym_sexp, Enum):
            enum = sym_sexp
            # enum_members = sym_sexp.members
            # lset = enum_members.difference(lset)
            # return Or(*[Eq(enum.var, enum.member_vars[lit]) for lit in lset])
            return EnumIn(enum.var, lset, nin=True)
        else:
            if isinstance(sym_sexp, tuple):
                sym = self.handle_symbol(*sym_sexp)
            else:
                sym = self.handle_atoms(sym_sexp)

            return Or(*[Ne(sym, lit) for lit in lset])

    @Lisp.handle('symbol', leafs=Lisp.ALL)
    def handle_symbol(self, _, sym, typ):
        if isinstance(sym, Symbol):
            return sym
        elif isinstance(sym, Enum):
            return sym.var
        else:
            if typ == 'string':
                return Symbol(sym, integer=True, finite=True)
            elif typ == 'number':
                return Symbol(sym, real=True, finite=True)
            elif typ == 'boolean':
                return Symbol(sym, bool=True)
            else:
                return Symbol(sym)

    @Lisp.handle(lambda x: is_atom(x) or isinstance(x, Enum))
    def handle_atoms(self, a):
        if type(a) == int:
            return Integer(a)
        elif type(a) == float:
            return Float(a)
        elif type(a) == bool:
            return a
        elif type(a) == str:
            return Symbol(a, integer=True, finite=True)
        elif isinstance(a, Enum):
            return a.var
        else:
            raise ValueError(f"Cannot convert atom to sympy symbol: {a}")
