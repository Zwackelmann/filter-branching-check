from fbc.lisp.core import Lisp, is_atom, is_enum_sexp, sexp_like, sexp_type
from fbc.algebra.core import ExplOps


class Compiler(Lisp):
    """
    - Resolves 'lookup's by resolving variables in the lisps scope
    - applies macros
    - Resolves arithmetic expressions only containing atoms
    """

    @Lisp.handle('lookup', leafs=Lisp.ALL)
    def handle_lookup(self, _, ident):
        """
        Syntax: ('lookup', ['ident_1', ..., 'ident_n'])

        Resolves a variable by looking up the identifier in the Lisp's scope. The resolved result must be an sexp.

        Depending on the type of value returned by the scope it is converted into an sexp:
          (1) If the returned value is an atom or tuple, the value is returned as is

          (2) If the returned value is an `sexp_like` (i.e. an object containing a `to_sexp` function), the return
              value of `to_sexp` will be returned

          (3) If the returned value is any other python object, the object `obj` is returned as  ('py_obj', obj)

        :param _: not  used
        :param ident: identifier list
        :return: resolved sexp
        """    """
    Scope 
    """
        res = self.scope[ident]
        if is_atom(res) or isinstance(res, tuple):
            return res
        elif sexp_like(res):
            return res.to_sexp()
        else:
            return 'py_obj', res

    @Lisp.handle('call')
    def handle_call_macro(self, _, fun, fun_args):
        """
        Syntax: ('call' ('macro', ['type_1', ..., 'type_n'], `handle`), ['arg_1', ..., 'arg_n'])

        Applies the macro handle with given arguments

        :param _: not used
        :param fun: function definition as tuple consisting of:
                     - function type as string (must be 'macro' to be applied here)
                     - signature as list of strings
                     - function handle as python callable
        :param fun_args: arbitrary list of arguments for the macro
        :return: macro return value
        """
        fun_type, exp_sexp_types, macro_handle = fun

        if fun_type != 'macro':
            return Lisp.NOOP

        arg_sexp_types = [sexp_type(a) for a in fun_args]
        if not len(arg_sexp_types) == len(exp_sexp_types) and \
                all([a == b for a, b in zip(arg_sexp_types, exp_sexp_types)]):
            raise ValueError(f"Error when calling macro. Expected [{str(exp_sexp_types)}] got "
                             f"[{str(arg_sexp_types)}]")

        return macro_handle(*fun_args)

    @Lisp.handle(ExplOps.binary_arith, default=Lisp.NOOP)
    def handle_binary_arith_ops(self, op, *operands):
        """
        Syntax: ('<op>', <lop>, <rop>) e.g. ('+', 1, 2)

        Applies the operation on the operands, if all operands are number atoms

        :param op: operator
        :param operands: list of operand
        :return: result
        """
        # evaluate arithmetic ops containing only atoms
        if all([sexp_type(o) == 'number' for o in operands]):
            return ExplOps.binary_arith[op](*operands)
        elif op == '+' and all([sexp_type(o) == 'string' for o in operands]):
            return "".join(operands)

    @Lisp.handle(ExplOps.unary_arith, default=Lisp.NOOP)
    def handle_unary_arith_ops(self, op, lop):
        """
        Syntax: ('<op>', <lop>) e.g. ('neg', 1)

        Applies the operation on the operand, if the operand is a number atom

        :param op: operator
        :param lop: left operand
        :return: result
        """
        # evaluate arithmetic ops containing only atoms
        if sexp_type(lop) == 'number':
            return ExplOps.unary_arith[op](lop)


class TypeResolver(Lisp):
    """
    Resolves the type of an sexp
    """

    @Lisp.handle(ExplOps.unary_logic)
    def handle_unary_logic_ops(self, _, ltype):
        if ltype != 'boolean':
            raise ValueError(f"expected type boolean but got {ltype}")

        return 'boolean'

    @Lisp.handle(ExplOps.binary_logic)
    def handle_binary_logic_ops(self, op, *op_types):
        if not all([t == 'boolean' for t in op_types]):
            raise ValueError(f"expected boolean operands in {(op, op_types)}")

        return 'boolean'

    @Lisp.handle(ExplOps.relation)
    def handle_relation_ops(self, op, ltype, rtype):
        if ltype != rtype:
            raise ValueError(f"data types are not equal in {(op, ltype, rtype)}")

        return 'boolean'

    @Lisp.handle(ExplOps.binary_arith)
    def handle_binary_arith_ops(self, op, *op_types):
        if not all([t == 'number' for t in op_types]):
            raise ValueError(f"{(op, op_types)} contains an unexpected type")

        return 'number'

    @Lisp.handle(ExplOps.unary_arith)
    def handle_unary_arith_ops(self, op, ltype):
        if not all([o in ['number'] for o in [ltype]]):
            raise ValueError(f"{(op, ltype)} contains an unexpected type")

        return 'number'

    @Lisp.handle('symbol', leafs=Lisp.ALL)
    def handle_symbol(self, _, __, stype):
        return stype

    @Lisp.handle(is_atom)
    def handle_atom(self, a):
        return sexp_type(a)


class ResolveEnums(Lisp):
    """
    Macro handling predicates containing an enumeration.

    Enums are replaced in expressions like `('=', ('symbol', 'enum_123', 'number'), 1)`. The macro is applied, if
    (1) one side of the (in)equation is a symbol with a name that is contained in `ENUM`. In above example
        `ENUM.enum_123` must be defined in scope. Otherwise, the macro will not be applied
    (2) The other side must be a literal

    If both conditions are met, the name of the symbol sexp is replaced with the sympy enum variable defined by the
    enum object and the literal is replaced with a symbol sexp containing the respective sympy literal variable from
    the enum object.

    inequation predicates are converted into a disjunction of equation predicates by filtering all literals from the
    enum domain set that satisfy the in inequation.
    """

    @Lisp.handle(ExplOps.relation, default=Lisp.NOOP)
    def handle_relation_ops(self, op, lop, rop):
        enums = self.scope['ENUM']

        if is_enum_sexp(lop, enums) and is_atom(rop):
            sym_sexp = lop
            lit = rop
        elif is_atom(lop) and is_enum_sexp(rop, enums):
            lit = lop
            sym_sexp = rop
        else:
            return Lisp.NOOP

        _, sym_name, sym_type = sym_sexp
        lit_type = TypeResolver.eval(lit)
        enum = enums[sym_name]

        if sym_type != lit_type:
            raise ValueError(f"types incompatible in {(op, lop, rop)}. {sym_type} != {lit_type}")

        ops = {**ExplOps.inequation, "!=": ExplOps.relation['!=']}
        if op in ops:
            if not (lit_type == sym_type == enum.typ == 'number'):
                raise ValueError(f"inequation with enum type can only be resolved with numbers")

            ineq = ops[op]
            valid_lit = [e for e in enum if ineq(e, lit)]
            lit_symbols = [('symbol', enum.member_vars[li], lit_type) for li in valid_lit]

            if len(lit_symbols) == 0:
                raise ValueError("empty set of literals after resolving inequation")

            eq_sexps = [("==", ('symbol', enum.var, lit_type), li) for li in lit_symbols]
            if len(eq_sexps) == 1:
                return eq_sexps[0]
            else:
                or_sexp = ('or', eq_sexps[0], eq_sexps[1])
                for eq_sexp in eq_sexps[2:]:
                    or_sexp = ('or', or_sexp, eq_sexp)
                return or_sexp
        else:
            if lit not in enum:
                raise ValueError(f"{sym_name} must be one of {enum}. Found {lit}")

            return op, ('symbol', enum.var, lit_type), ('symbol', enum.member_vars[lit], lit_type)

    @Lisp.handle(lambda *_: True, leafs=Lisp.ALL)
    def ignore_rest(self, *_):
        return Lisp.NOOP


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
