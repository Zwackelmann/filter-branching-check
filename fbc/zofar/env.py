from sympy import evaluate as sympy_evaluate, And, true, Not, simplify
from fbc.lisp.core import Lisp, DictScope
from fbc.zofar.lisp import Compiler, TypeResolver, ZofarVariable, ZofarModule, ResolveEnums
from fbc.zofar.parse import parse_spring_sexp
from fbc.algebra.core import Enum
from fbc.algebra.eval import AlgInterpreter
from functools import cached_property
from typing import Dict, List
from fbc.zofar.io import xml
from fbc.util import flatten, group_by
import networkx as nx


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
            uid_enum = Enum(var, v, 'string')
            number_enum = Enum(f"{var}_NUM", n, 'number')
            enums = {**enums, **{var: uid_enum, f"{var}_NUM": number_enum}}

    return enums


class QuestionnaireEnv:
    def __init__(self, variables: Dict[str, ZofarVariable], enums: Dict[str, Enum], macros=None):
        if macros is None:
            macros = []

        self.variables = variables
        self.enums = enums
        self.macros = macros

    @cached_property
    def scope(self):
        return DictScope({**self.variables, **{'zofar': ZofarModule.new_dict_scope(), 'ENUM': self.enums}})

    def eval(self, s):
        sexp = parse_spring_sexp(s)

        for macro in self.macros:
            if isinstance(macro, type) and issubclass(macro, Lisp):
                sexp = macro.eval(sexp, self.scope)
            elif callable(macro):
                sexp = macro(sexp, self.scope)
            else:
                raise ValueError(f"unexpected macro type: {type(macro)}")

        typ = TypeResolver.eval(sexp)

        if typ != 'boolean':
            raise ValueError("type check for transition does not result in boolean")

        with sympy_evaluate(False):
            expr = AlgInterpreter.eval(sexp)

        expr.doit()
        return expr

    def __call__(self, s):
        return self.eval(s)

    @classmethod
    def from_questionnaire(cls, q: xml.Questionnaire, macros=None):
        if macros is None:
            macros = []

        enums = enum_dict(q.pages)
        variables = {v.name: ZofarVariable.from_variable(v) for v in q.variables.values()}

        return QuestionnaireEnv(variables, enums, macros)


def construct_graph(q: xml.Questionnaire):
    evaluator = QuestionnaireEnv.from_questionnaire(q, [Compiler, ResolveEnums])

    g = nx.DiGraph()
    g.add_nodes_from([p.uid for p in q.pages])

    edges = []
    for page in q.pages:
        neg_trans_filters = []
        for trans in page.transitions:
            if trans.condition is not None:
                trans_filter = evaluator(trans.condition)
            else:
                trans_filter = true

            excluding_trans_filter = simplify(And(*neg_trans_filters + [trans_filter]))
            edges.append((page.uid, trans.target_uid, {'filter': excluding_trans_filter}))
            neg_trans_filters.append(Not(trans_filter))

    g.add_edges_from(edges)

    return g
