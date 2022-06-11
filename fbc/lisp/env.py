from sympy import evaluate as sympy_evaluate
from fbc.lisp.core import Lisp
from fbc.lisp.macros import TypeResolver
from fbc.algebra.eval import AlgInterpreter


class LispEnv:
    def __init__(self, sexp_parser, scope, macros=None):
        if macros is None:
            macros = []

        self.sexp_parser = sexp_parser
        self.scope = scope
        self.macros = macros

    def apply_macros(self, sexp):
        for macro in self.macros:
            if isinstance(macro, type) and issubclass(macro, Lisp):
                sexp = macro.eval(sexp, self.scope)
            elif callable(macro):
                sexp = macro(sexp, self.scope)
            else:
                raise ValueError(f"unexpected macro type: {type(macro)}")

        return sexp

    @classmethod
    def verify_sexp(cls, sexp):
        typ = TypeResolver.eval(sexp)

        if typ != 'boolean':
            raise ValueError("type check for transition does not result in boolean")

        return True

    @classmethod
    def convert_sexp(cls, sexp):
        with sympy_evaluate(False):
            expr = AlgInterpreter.eval(sexp)

        expr.doit()
        return expr

    def eval(self, s):
        sexp = self.sexp_parser(s)
        sexp = self.apply_macros(sexp)

        self.verify_sexp(sexp)
        return self.convert_sexp(sexp)

    def __call__(self, s):
        return self.eval(s)
