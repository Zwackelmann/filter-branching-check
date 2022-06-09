import pyparsing as pp
from fbc.lisp.core import infix_to_sexp

pp.ParserElement.enablePackrat()


class SpringSexpParser:
    """
    Parses spring expressions and returns them as an sexp expression
    """
    def __init__(self):
        self.keywords = {'true', 'false', 'gt', 'ge', 'lt', 'le', 'and', 'or'}
        self.scoped_identifier = pp.delimited_list(pp.common.identifier, delim='.') \
            .add_condition(lambda t: all([_t not in self.keywords for _t in t.as_list()])) \
            .add_parse_action(lambda t: ('lookup', t.as_list()))

        self.bool_lit = pp.one_of(["true", "false"]).set_parse_action(lambda t: t[0] == "true")

        self.term_plain = pp.Forward()

        self.term = pp.infix_notation(self.term_plain, [
            ('-', 1, pp.opAssoc.RIGHT, lambda t: ('neg', t[0][1])),
            ('*', 2, pp.opAssoc.LEFT, lambda t: infix_to_sexp(t[0])),
            ('/', 2, pp.opAssoc.LEFT, lambda t: infix_to_sexp(t[0])),
            ('+', 2, pp.opAssoc.LEFT, lambda t: infix_to_sexp(t[0])),
            ('-', 2, pp.opAssoc.LEFT, lambda t: infix_to_sexp(t[0])),
        ])

        self.predicate = (
                self.term('lterm') +
                pp.one_of(["gt", "ge", "lt", "le", "==", "!="])("pred") +
                self.term('rterm')
        ).set_parse_action(lambda t: (t['pred'], t['lterm'], t['rterm']))
        self.bool_exp_plain = pp.Forward()

        self.bool_exp = pp.infix_notation(self.bool_exp_plain, [
            ('!', 1, pp.opAssoc.RIGHT, lambda t: ('not', t[0][1])),
            ('and', 2, pp.opAssoc.LEFT, lambda t: infix_to_sexp(t[0])),
            ('or', 2, pp.opAssoc.LEFT, lambda t: infix_to_sexp(t[0]))
        ])

        self.function_argument = self.bool_exp | self.term | self.scoped_identifier
        self.function_call = (
                self.scoped_identifier +
                pp.Group(pp.Suppress("(") + pp.delimited_list(self.function_argument) + pp.Suppress(")"))
        ).set_parse_action(lambda t: ('call', t[0], t[1].as_list()))

        self.term_plain <<= (pp.common.number | pp.sgl_quoted_string | self.function_call | self.scoped_identifier)
        self.bool_exp_plain <<= (self.bool_lit | self.predicate | self.function_call | self.scoped_identifier)\
            .set_parse_action(lambda t: t[0])

    def parse(self, s):
        """
        Parses given spring expression and converts it into an sexp expression

        :param s: spring expression
        :return: sexp expression
        """
        return self.bool_exp.parse_string(s, parse_all=True)[0]


_DEFAULT_PARSER = None


def default_parser():
    global _DEFAULT_PARSER
    if _DEFAULT_PARSER is None:
        _DEFAULT_PARSER = SpringSexpParser()

    return _DEFAULT_PARSER


def parse_spring_sexp(s):
    return default_parser().parse(s)
