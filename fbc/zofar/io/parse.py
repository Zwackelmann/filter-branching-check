import pyparsing as pp
from fbc.lisp.core import infix_to_sexp

pp.ParserElement.enablePackrat()


class SpringSexpParser:
    """
    Parses spring expressions and returns them as an sexp expression
    """
    def __init__(self):
        self.keywords = {k: pp.Keyword(k) for k in ['true', 'false', 'gt', 'ge', 'lt', 'le', 'and', 'or']}
        any_keyword = pp.MatchFirst(self.keywords.values())
        LPAR, RPAR = map(pp.Suppress, "()")

        self.identifier = (~any_keyword + pp.Word(pp.alphas, pp.alphanums + "_")).set_name("identifier")

        self.scoped_identifier = pp.delimited_list(self.identifier, delim='.') \
            .add_parse_action(lambda t: ('lookup', t.as_list())) \
            .set_name("scoped_identifier")

        self.expr = pp.Forward().set_name("expression")

        self.bool_lit = pp.MatchFirst([self.keywords['true'], self.keywords['false']]) \
            .set_parse_action(lambda t: t[0] == "true")\
            .set_name('bool_lit')

        self.function_call = (
                self.scoped_identifier +
                pp.Group(LPAR + pp.delimited_list(self.expr) + RPAR)
        ).set_parse_action(lambda t: ('call', t[0], t[1].as_list()))

        self.expr_term = (
            pp.common.number |
            self.bool_lit |
            self.function_call |
            pp.sgl_quoted_string |
            self.scoped_identifier
        )

        unary_ops = {"-": 'neg', '+': 'pos', "!": 'not'}

        self.expr << pp.infix_notation(
            self.expr_term,
            [
                (pp.one_of(unary_ops.keys()), 1, pp.opAssoc.RIGHT, lambda t: (unary_ops[t[0][0]], t[0][1])),
                (pp.one_of('* /'), 2, pp.opAssoc.LEFT, lambda t: infix_to_sexp(t[0])),
                (pp.one_of('+ -'), 2, pp.opAssoc.LEFT, lambda t: infix_to_sexp(t[0])),
                (pp.one_of('gt ge lt le == !='), 2, pp.opAssoc.LEFT, lambda t: infix_to_sexp(t[0])),
                (pp.one_of('and'), 2, pp.opAssoc.LEFT, lambda t: infix_to_sexp(t[0])),
                (pp.one_of('or'), 2, pp.opAssoc.LEFT, lambda t: infix_to_sexp(t[0]))
            ]
        )

    def parse(self, s):
        """
        Parses given spring expression and converts it into an sexp expression

        :param s: spring expression
        :return: sexp expression
        """

        return self.expr.parse_string(s, parse_all=True)[0]
