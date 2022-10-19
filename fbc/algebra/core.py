from sympy import true, false, Symbol, Eq, Not, And, Lt, Le, Gt, Ge, Ne, Or, Add, Mul, Pow, FiniteSet, Basic
from sympy.logic.boolalg import Boolean, is_literal, simplify_logic
from functools import reduce
from typing import Iterable, Set, Dict
from itertools import product


class AlgOps:
    inequation = {'lt': lambda x, y: Lt(x, y),
                  'le': lambda x, y: Le(x, y),
                  'gt': lambda x, y: Gt(x, y),
                  'ge': lambda x, y: Ge(x, y)}

    equal = {"==": lambda x, y: Eq(x, y),
             "!=": lambda x, y: Ne(x, y)}

    relation = {**inequation, **equal}

    binary_logic = {"and": lambda *args: And(*args),
                    "or": lambda *args: Or(*args)}

    unary_logic = {'not': lambda a: Not(a)}

    binary_arith = {'+': lambda *args: Add(*args),
                    '-': lambda *args: Add(*([args[0]] + [Mul(a, -1) for a in args[1:]])),
                    '*': lambda *args: Mul(*args),
                    '/': lambda *args: Mul(*([args[0]] + [Pow(a, -1) for a in args[1:]]))}

    unary_arith = {'neg': lambda a: -a}


class ExplOps:
    inequation = {'lt': lambda x, y: x < y,
                  'le': lambda x, y: x <= y,
                  'gt': lambda x, y: x > y,
                  'ge': lambda x, y: x >= y}

    equal = {'==': lambda x, y: x == y,
             '!=': lambda x, y: x != y}

    relation = {**inequation, **equal}

    binary_logic = {'and': lambda *args: reduce(lambda a, b: a and b, args),
                    'or': lambda *args: reduce(lambda a, b: a or b, args)}

    unary_logic = {'not': lambda a: not a}

    binary_arith = {'+': lambda *args: reduce(lambda a, b: a + b, args),
                    '-': lambda *args: reduce(lambda a, b: a - b, args),
                    '*': lambda *args: reduce(lambda a, b: a * b, args),
                    '/': lambda *args: reduce(lambda a, b: a / b, args)}

    unary_arith = {'neg': lambda a: -a}


class Enum:
    """
    Defines an enumeration with a finite set of members.
    """

    def __init__(self, name: str, members: Iterable[int]):
        """
        Initialize an enumeration

        :param name: name of the enumeration
        :param members: list of enum members
        """

        self.name = name

        self.var = EnumSymbol(name, self)

        self.members: Set[int] = set(members)
        self.member_vars: Dict[int, EnumLiteral] = {m: EnumLiteral(f"LIT_{name}_{m}", self) for m in members}

    def subs(self, m):
        """
        Returns a substitution dict replacing the enum variable with the given member

        :param m: member
        :return: substitution dict
        """
        return {self.name: self.member_vars[m]}

    @property
    def null_subs(self):
        """
        Returns a substitution dict replacing the enum variable and all enum literals with false.
        Using this substitution the enum is effectively removed from the equation.

        :return: substitution dict
        """
        return {**{self.name: false}, **{f"{self.name}_{m}": false for m in self.member_vars}}

    def eq(self, m):
        """
        Returns predicate checking if the enum variable is equal to the given member

        :param m: member
        :return: predicate
        """
        return Eq(self.var, self.member_vars[m])

    def __str__(self):
        return f"{self.name}({[m for m in self.member_vars.keys()]})"

    def __repr__(self):
        return str(self)

    def __contains__(self, item):
        return item in self.members

    def __iter__(self):
        return iter(self.members)


class EnumSymbol(Symbol):
    def __new__(cls, name: str, enum: Enum, **assumptions):
        sym = Symbol.__new__(cls, name, integer=True, **assumptions)
        sym.enum = enum
        sym._args = ()
        return sym


class EnumLiteral(Symbol):
    def __new__(cls, name: str, enum: Enum, **assumptions):
        sym = Symbol.__new__(cls, name, integer=True, **assumptions)
        sym.enum = enum
        sym._args = ()
        return sym


class EnumIn(Boolean):
    def __new__(cls, esym: EnumSymbol, lset, nin=False, **options):
        lset = FiniteSet(*lset)

        enum_in = Boolean.__new__(cls, esym, lset)
        enum_in.esym = esym
        enum_in.lset = lset

        if nin:
            enum_in = EnumIn.reversed(enum_in)

        if len(enum_in.lset) == 0:
            return false
        elif enum_in.esym.enum.members == set(lset):
            return true
        else:
            return enum_in

    def reversed(self):
        all_members = self.esym.enum.members
        inst_members = set(self.lset)

        lset = all_members.difference(inst_members)

        return EnumIn(self.esym, lset)

    def _eval_simplify(self, **_):
        return self


def simplify_or(or_inst: Basic) -> Basic:
    if not isinstance(or_inst, Or):
        return or_inst

    ins = {}
    out_terms = []
    for arg in or_inst.args:
        if isinstance(arg, EnumIn):
            if arg.esym in ins:
                ins[arg.esym] = ins[arg.esym].union(set(arg.lset.args))
            else:
                ins[arg.esym] = set(arg.lset.args)
        else:
            out_terms.append(arg)

    for esym in ins.keys():
        out_terms.append(EnumIn(esym, ins[esym]))

    if len(out_terms) == 1:
        return out_terms[0]
    else:
        return Or(*out_terms)


def simplify_and(and_inst: Basic) -> Basic:
    if not isinstance(and_inst, And):
        return and_inst

    ins = {}
    out_terms = []
    for arg in and_inst.args:
        if isinstance(arg, EnumIn):
            if arg.esym in ins:
                ins[arg.esym] = ins[arg.esym].intersection(set(arg.lset.args))
            else:
                ins[arg.esym] = set(arg.lset.args)
        else:
            out_terms.append(arg)

    for esym in ins.keys():
        out_terms.append(EnumIn(esym, ins[esym]))

    if len(out_terms) == 1:
        return out_terms[0]
    else:
        return And(*out_terms)


def simplify_not(not_inst: Basic) -> Basic:
    if not isinstance(not_inst, Not):
        return not_inst

    if len(not_inst.args) != 1:
        raise ValueError("Not instance must have exactly one argument")

    arg = not_inst.args[0]

    if isinstance(arg, EnumIn):
        return arg.reversed()
    else:
        return not_inst


def simplify_enum(expr: Basic) -> Basic:
    if isinstance(expr, Boolean):
        if expr.is_Atom or is_literal(expr):
            return expr

        expr = expr.func(*[simplify_enum(arg) for arg in expr.args])

        if isinstance(expr, And):
            return simplify_and(expr)
        elif isinstance(expr, Or):
            return simplify_or(expr)
        elif isinstance(expr, Not):
            return simplify_not(expr)
        else:
            return expr
    else:
        return expr


def simplify_enum_subsets(expr: Basic) -> Basic:
    if isinstance(expr, Boolean):
        if expr.is_Atom or is_literal(expr):
            return expr

        enum_ins = expr.find(EnumIn)

        for e1, e2 in product(enum_ins, enum_ins):
            if not (e1.esym == e2.esym and e1.lset != e2.lset and e1.lset.intersection(e2.lset) == e2.lset):
                # if e1's lset is a true superset of e2's lset
                continue

            # replace e1 with an or predicate
            e1_diff = EnumIn(e1.esym, set(e1.lset).difference(set(e2.lset)))
            e1_repl = Or(e2, e1_diff)

            expr_repl = simplify_logic(expr.replace(e1, e1_repl))
            if expr_repl.count_ops() < expr.count_ops():
                return simplify_enum_subsets(expr_repl)

        return expr
    else:
        return expr
