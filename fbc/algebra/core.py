from sympy import false, Symbol
from sympy import Eq, Not, And, Lt, Le, Gt, Ge, Ne, Or


class AlgOps:
    inequation = {'lt': lambda x, y: Lt(x, y),
                  'le': lambda x, y: Le(x, y),
                  'gt': lambda x, y: Gt(x, y),
                  'ge': lambda x, y: Ge(x, y)}

    equal = {"==": lambda x, y: Eq(x, y),
             "!=": lambda x, y: Ne(x, y)}

    relation = {**inequation, **equal}

    binary_logic = {"and": lambda a, b: And(a, b),
                    "or": lambda a, b: Or(a, b)}

    unary_logic = {'not': lambda a: Not(a)}

    binary_arith = {'+': lambda a, b: a + b,
                    '-': lambda a, b: a - b,
                    '*': lambda a, b: a * b,
                    '/': lambda a, b: a / b}

    unary_arith = {'neg': lambda a: -a}


class ExplOps:
    inequation = {'lt': lambda x, y: x < y,
                  'le': lambda x, y: x <= y,
                  'gt': lambda x, y: x > y,
                  'ge': lambda x, y: x >= y}

    equal = {'==': lambda x, y: x == y,
             '!=': lambda x, y: x != y}

    relation = {**inequation, **equal}

    binary_logic = {'and': lambda a, b: a and b,
                    'or': lambda a, b: a or b}

    unary_logic = {'not': lambda a: not a}

    binary_arith = {'+': lambda a, b: a + b,
                    '-': lambda a, b: a - b,
                    '*': lambda a, b: a * b,
                    '/': lambda a, b: a / b}

    unary_arith = {'neg': lambda a: -a}


class Enum:
    """
    Defines an enumeration with a finite set of members.
    """

    def __init__(self, name, members, typ=None):
        """
        Initialize an enumeration

        :param name: name of the enumeration
        :param members: list of enum members
        :param typ: type of enum (must be one of ['string', 'number', None])
        """
        if typ not in ['string', 'number', None]:
            raise ValueError("typ must be one of ['string', 'number', None]")

        self.name = name

        self.var = Symbol(name, integer=True)

        self.members = set(members)
        self.member_vars = {m: Symbol(f"LIT_{name}_{m}", integer=True) for m in members}
        self.typ = typ

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
