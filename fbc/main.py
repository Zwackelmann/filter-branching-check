from fbc.zofar.io.xml import read_questionnaire
from fbc.zofar.module import zofar_graph, zofar_env
from fbc.zofar.io.parse import SpringSexpParser
from fbc.util import timer
from fbc.graph import draw_graph, graph_soundness_check, evaluate_node_predicates, transition_graph, show_graph
from fbc.lisp.core import Lisp, sexp_type, is_atom
from fbc.lisp.macros import Simplify, ResolveEnums
from sympy import Symbol, Add, Mul, Eq, Rel, Integer, And, Or, Tuple, FiniteSet, Atom, Gt, Not, true, simplify
from fbc.algebra.eval import AlgInterpreter
from fbc.algebra.core import ExplOps, AlgOps, Enum, EnumSymbol, simplify_enum, EnumIn, simplify_and, simplify_or, \
    simplify_not, simplify_enum_subsets
import sympy
from sympy.logic.boolalg import to_dnf, is_literal, BooleanFunction, to_cnf


def main2():
    monkey_patch_not_nnf()
    monkey_patch_and_eval_simplify()
    monkey_patch_boolean_function_eval_simplify()
    monkey_patch_or_eval_simplify()
    monkey_patch_not_eval()

    [e1, e2] = [Enum(x, {1, 2, 3, 4}) for x in ["e1", "e2"]]

    # [a, b, c] = [('symbol', x, 'boolean') for x in ['a', 'b', 'c', 'd', 'e']]
    [a, b, c] = [Symbol(x, boolean=True) for x in ['a', 'b', 'c']]
    # [i, j, k] = [Symbol(x, integer=True) for x in ['f', 'g', 'h', 'i', 'j']]
    [i, j, k] = [Symbol(x, boolean=True) for x in ['i', 'j', 'k']]

    # sexp = ('or', ('not', ('in', e1, {1, 2})), ('in', e1, {2, 3}), ('in', e2, {1, 2}), ('in', e2, {3, 4}))
    # sexp = ('or', ('and', ('in', e1, {3, 4})))

    # ex = AlgInterpreter.eval(sexp)

    transitions = {
        'a': [(And(EnumIn(e1.var, {1, 2}), i > 0), 'b'), (EnumIn(e1.var, {3}), 'c'), (Or(EnumIn(e1.var, {4}), i <=0), 'b'), (true, 'd')],
        'b': [(true, 'e')],
        'c': [(true, 'e')],
        'd': [(true, 'e')]
    }

    g = transition_graph(transitions)
    ex = g.edges['a', 'b']['filter']

    enum_ins = ex.find(EnumIn)

    show_graph(g)

    # print(AlgInterpreter.eval(sexp2))
    #  print(to_dnf(AlgInterpreter.eval(sexp)) == to_dnf(AlgInterpreter.eval(sexp2)))


def monkey_patch_and_eval_simplify():
    super_eval_simplify = And._eval_simplify

    def _eval_simplify(self, **kwargs):
        rv = super_eval_simplify(self, **kwargs)

        if isinstance(rv, And):
            rv = simplify_and(rv)
        elif isinstance(rv, Or):
            rv = simplify_or(rv)
        elif isinstance(rv, Not):
            rv = simplify_not(rv)
        else:
            pass

        return rv

    And._eval_simplify = _eval_simplify


def monkey_patch_or_eval_simplify():
    super_eval_simplify = Or._eval_simplify

    def _eval_simplify(self, **kwargs):
        rv = super_eval_simplify(self, **kwargs)

        if isinstance(rv, And):
            rv = simplify_and(rv)
        elif isinstance(rv, Or):
            rv = simplify_or(rv)
        elif isinstance(rv, Not):
            rv = simplify_not(rv)
        else:
            pass

        return rv

    Or._eval_simplify = _eval_simplify


def monkey_patch_boolean_function_eval_simplify():
    super_eval_simplify = BooleanFunction._eval_simplify

    def _eval_simplify(self, **kwargs):
        if isinstance(self, And):
            rv = simplify_and(self)
        elif isinstance(self, Or):
            rv = simplify_or(self)
        elif isinstance(self, Not):
            rv = simplify_not(self)
        else:
            rv = self

        rv = super_eval_simplify(rv, **kwargs)

        if isinstance(rv, And):
            rv = simplify_and(rv)
        elif isinstance(rv, Or):
            rv = simplify_or(rv)
        elif isinstance(rv, Not):
            rv = simplify_not(rv)
        else:
            pass

        rv = simplify_enum_subsets(rv)

        return rv

    BooleanFunction._eval_simplify = _eval_simplify


def monkey_patch_not_nnf():
    super_nnf = Not.to_nnf

    def _to_nnf(self, simplify=True):
        if is_literal(self):
            return self

        expr = self.args[0]
        if isinstance(expr, EnumIn):
            return expr.reversed()
        else:
            return super_nnf(self, simplify)

    Not.to_nnf = _to_nnf


def monkey_patch_not_eval():
    super_eval = Not.eval

    def _eval(*args):
        if isinstance(args[0], EnumIn):
            return args[0].reversed()
        else:
            return super_eval(*args)

    Not.eval = _eval


def main():
    monkey_patch_not_nnf()
    monkey_patch_and_eval_simplify()
    monkey_patch_boolean_function_eval_simplify()
    monkey_patch_or_eval_simplify()
    monkey_patch_not_eval()

    q = read_questionnaire("data/questionnaire2.xml")
    with timer() as t:
        env, g = zofar_graph(q)
        print(t)
    enums = list(env.scope['ENUM'].values())

    # print(graph_soundness_check(g, 'index', enums))

    evaluate_node_predicates(g, 'index', enums)
    draw_graph(g, 'graph.png')

    # p = SpringSexpParser()

    # trans_dict = {page.uid: [(trans.condition, trans.target_uid) for trans in page.transitions] for page in q.pages}
    # result = PoolProcess.process_batch(ParserHandle(p), trans_dict)
    # print(result)


if __name__ == "__main__":
    main()



