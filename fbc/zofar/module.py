from fbc.lisp.core import DictScope, Macro, Scope
from fbc.lisp.env import LispEnv
from fbc.lisp.macros import Compiler, ResolveEnums, Simplify
from fbc.zofar.io.parse import SpringSexpParser
from fbc.graph import transition_graph
from typing import Any, Tuple
from fbc.algebra.core import Enum
from typing import List
from fbc.zofar.io import xml
from fbc.util import flatten, group_by, PoolProcess
import networkx as nx
from sympy import true


class ZofarModule:
    @classmethod
    def new_dict_scope(cls):
        return DictScope({
            'asNumber': Macro(['py_obj'], ZofarModule.as_number),
            'isMissing': Macro(['py_obj'], ZofarModule.is_missing),
            'baseUrl': Macro([], ZofarModule.base_url),
            'isMobile': Macro([], ZofarModule.is_mobile)
        })

    @classmethod
    def as_number(cls, sexp: tuple):
        if not isinstance(sexp, tuple) or sexp[0] != 'py_obj':
            raise ValueError("`sexp` must be a 'py_obj'")

        _, obj = sexp

        if not isinstance(obj, ZofarVariable):
            raise ValueError(f'can only transform `ZofarVariable`s into numbers. Not {type(obj)}')

        if obj.value_type == 'number':
            sym_name = obj.name
        else:
            sym_name = f"{obj.name}_NUM"

        return 'symbol', sym_name, 'number'

    @classmethod
    def is_missing(cls, sexp):
        if not isinstance(sexp, tuple) or sexp[0] != 'py_obj':
            raise ValueError("`sexp` must be a 'py_obj'")

        _, obj = sexp

        if not isinstance(obj, ZofarVariable):
            raise ValueError(f'can only transform `ZofarVariable`s into numbers. Not {type(obj)}')

        return 'symbol', f"{obj.name}_IS_MISSING", 'boolean'

    @classmethod
    def base_url(cls):
        return 'symbol', "ZOFAR_BASE_URL", 'string'

    @classmethod
    def is_mobile(cls):
        return 'symbol', "ZOFAR_IS_MOBILE", 'boolean'


class ZofarVariable(Scope):
    PROPERTIES = {'value'}
    MEMBERS = {}

    def __init__(self, name: str, value_type: str):
        self.name = name
        self.value_type = value_type

    def _lookup(self, ident: str) -> Any:
        if ident in ZofarVariable.PROPERTIES:
            return getattr(self, ident)()
        elif ident in ZofarVariable.MEMBERS:
            return getattr(self, ident)
        else:
            raise AttributeError(f'ZofarVariable has no attribute {ident}')

    def value(self):
        return 'symbol', self.name, self.value_type

    @classmethod
    def from_variable(cls, var: xml.Variable):
        if var.type == 'string':
            return StringVariable(var.name)
        elif var.type == 'number':
            return NumberVariable(var.name)
        elif var.type == 'boolean':
            return BooleanVariable(var.name)
        elif var.type == 'enum':
            return EnumVariable(var.name)
        else:
            raise ValueError(f"unknown variable type: {var.type}")


class StringVariable(ZofarVariable):
    def __init__(self, name: str):
        super().__init__(name, 'string')


class NumberVariable(ZofarVariable):
    def __init__(self, name: str):
        super().__init__(name, 'number')


class BooleanVariable(ZofarVariable):
    def __init__(self, name: str):
        super().__init__(name, 'boolean')


class EnumVariable(ZofarVariable):
    def __init__(self, name: str):
        super().__init__(name, 'string')


def enum_dict(pages: List[xml.Page]):
    evs_list = flatten([p.enum_values for p in pages])
    enum_maps = [(evs.variable.name, {ev.uid: ev.value for ev in evs.values}) for evs in evs_list]
    enum_map_groups = group_by(enum_maps, lambda x: x[0], lambda x: x[1])
    enum_map_groups = {c: (cgs[0] if all([cg == cgs[0] for cg in cgs[1:]]) else cgs)
                       for c, cgs in enum_map_groups.items()}
    invalid_enum_map_groups = [(c, cgs) for c, cgs in enum_map_groups.items() if isinstance(cgs, list)]
    valid_enum_map_groups = {c: cgs for c, cgs in enum_map_groups.items() if isinstance(cgs, dict)}

    if len(invalid_enum_map_groups) != 0:
        print(invalid_enum_map_groups)
        raise ValueError("found invalid enum")

    enums = {}
    for var, veg in valid_enum_map_groups.items():
        if len(veg) == 0:
            raise ValueError(f"Empty enum found: {var}")
        else:
            v, n = zip(*veg.items())
            uid_enum = Enum(var, v)
            number_enum = Enum(f"{var}_NUM", n)
            enums = {**enums, **{var: uid_enum, f"{var}_NUM": number_enum}}

    return enums


def parse_handle(env: LispEnv):
    def f(source, condition, target):
        if condition is None or condition.strip() == "":
            return source, true, target

        return source, env.eval(condition), target

    return f


def zofar_env(q: xml.Questionnaire) -> LispEnv:
    enums = enum_dict(q.pages)
    variables = {v.name: ZofarVariable.from_variable(v) for v in q.variables.values()}
    scope = DictScope({**variables, **{'zofar': ZofarModule.new_dict_scope(), 'ENUM': enums}})

    parser = SpringSexpParser()
    return LispEnv(sexp_parser=parser.parse, scope=scope, macros=[Compiler, Simplify, ResolveEnums])


def zofar_graph(q: xml.Questionnaire) -> Tuple[LispEnv, nx.DiGraph]:
    env = zofar_env(q)
    trans_dict = {page.uid: [(trans.condition, trans.target_uid) for trans in page.transitions] for page in q.pages}

    trans_dict = {p: [((True if c is None else env.eval(c)), t) for c, t in trans] for p, trans in trans_dict.items()}

    return env, transition_graph(trans_dict)
