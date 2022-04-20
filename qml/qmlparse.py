import parsimonious.exceptions
from parsimonious.grammar import Grammar

grammar_zofar = Grammar(
    r""" # Test grammar
    expr = space or space
    or = and more_or
    more_or = ( space "or" space and )*
    and = term more_and
    more_and = ( space "and" space term )*
    term = not / value
    not = "!" space value
    value =  boolean / bracketed 
    boolean = "true" / "false" / evaluation
    evaluation = equals /unequals / greater_than / greater_equal / lesser_than / lesser_equal / function
    bracketed = "(" space expr space ")"
    equals =  function space "=="  space (literal / number / nil)
    unequals =  function space "!="  space (literal / number / nil)
    greater_than = function space "gt" space (literal / number)
    greater_equal = function space "ge" space (literal / number)
    lesser_than = function space "lt" space (literal / number)
    lesser_equal = function space "le" space (literal / number)
    function = zofar_function / zofar_value / zofar_set_counter / zofar_bool_set / const
    zofar_function = (~"zofar\.[a-zA-Z0-9]+\(" (varname) ")")
    #zofar_complex_function = (~"zofar.list(" (varname "," space)+ "),sessionController.getParticipant())
    zofar_set_counter = "zofar.isSetCounter(zofar.list(" varname ("," space varname space)* "),sessionController.getParticipant())"
    zofar_bool_set = "zofar.isBooleanSet('" varname "'," space "sessionController.participant)"
    zofar_nav_bean = "navigatorBean.isSame()" space
    const = zofar_nav_bean
    zofar_value = space varname ".value" 
    varname       = ~"[a-zA-Z0-9_]+"
    nil = "''"
    literal    = "'" chars "'"
    number = ~"[0-9]+"
    space    = ~"\s"*
    chars = ~"[^']*"

    """
)


def parse_zofar_code(input_str: str) -> parsimonious.nodes.Node:
    return grammar_zofar.parse(input_str)


if __name__ == '__main__':
    tree = parse_zofar_code('!(zofar.asNumber(var001) ge 2 and (((!var002.value or var003.value))))')
    print(tree)
