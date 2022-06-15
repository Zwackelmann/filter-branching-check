from fbc.zofar.io.xml import read_questionnaire
from fbc.zofar.module import zofar_graph
from fbc.zofar.io.parse import SpringSexpParser
from fbc.util import timer
from fbc.graph import draw_graph, graph_soundness_check, evaluate_node_predicates
from fbc.lisp.core import Lisp, sexp_type, is_atom
from fbc.algebra.eval import AlgInterpreter
from fbc.algebra.core import ExplOps, AlgOps
import sympy
from sympy.logic.boolalg import Equivalent, to_dnf


class ResolveNot(Lisp):
    @Lisp.handle("not")
    def handle_not(self, _, term):
        if sexp_type(term) == "not":
            return term[1]
        elif sexp_type(term) == "and":
            return "or", ResolveNot.eval(('not', term[1])), ResolveNot.eval(('not', term[2]))
        elif sexp_type(term) == "or":
            return "and", ResolveNot.eval(('not', term[1])), ResolveNot.eval(('not', term[2]))
        elif sexp_type(term) == "!=":
            return "==", term[1], term[2]
        elif sexp_type(term) == "==":
            return "!=", term[1], term[2]
        elif sexp_type(term) == "lt":
            return "ge", term[1], term[2]
        elif sexp_type(term) == "le":
            return "gt", term[1], term[2]
        elif sexp_type(term) == "gt":
            return "le", term[1], term[2]
        elif sexp_type(term) == "ge":
            return "lt", term[1], term[2]
        elif sexp_type(term) == 'symbol' or is_atom(term):
            return Lisp.NOOP
        else:
            raise ValueError("")

    @Lisp.handle('symbol', leafs=Lisp.ALL)
    def handle_symbol(self, *_):
        return Lisp.NOOP


def main():
    print(SpringSexpParser().parse("20 + 2 - 3 - 4 + 5 gt 10 and 1 == 1 and true"))


def main3():
    [a, b, c, d, e] = [('symbol', x, 'boolean') for x in ['a', 'b', 'c', 'd', 'e']]
    [f, g, h, i, j] = [('symbol', x, 'number') for x in ['f', 'g', 'h', 'i', 'j']]

    sexp = ('not', ('and', ('or', ("gt", f, 10), b), c))
    with timer() as t:
        sexp2 = ResolveNot.eval(sexp)
        print(t)

    print(sexp)
    print(AlgInterpreter.eval(sexp))
    print(sexp2)
    print(AlgInterpreter.eval(sexp2))
    print(to_dnf(AlgInterpreter.eval(sexp)) == to_dnf(AlgInterpreter.eval(sexp2)))


def main2():
    q = read_questionnaire("data/questionnaire.xml")
    with timer() as t:
        env, g = zofar_graph(q)
        print(t)
    enums = list(env.scope['ENUM'].values())

    print(graph_soundness_check(g, 'index', enums))

    evaluate_node_predicates(g, 'index', enums)
    draw_graph(g, 'graph.png')

    # p = SpringSexpParser()

    # trans_dict = {page.uid: [(trans.condition, trans.target_uid) for trans in page.transitions] for page in q.pages}
    # result = PoolProcess.process_batch(ParserHandle(p), trans_dict)
    # print(result)


if __name__ == "__main__":
    main()
