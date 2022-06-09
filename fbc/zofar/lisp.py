from fbc.lisp.core import Lisp, is_atom, DictScope, is_enum_sexp, Macro, Scope, sexp_like, sexp_type
from typing import Any
from fbc.algebra.core import ExplOps
from fbc.zofar.io import xml


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
    def handle_binary_arith_ops(self, op, lop, rop):
        """
        Syntax: ('<op>', <lop>, <rop>) e.g. ('+', 1, 2)

        Applies the operation on the operands, if all operands are number atoms

        :param op: operator
        :param lop: left operand
        :param rop: right operand
        :return: result
        """
        # evaluate arithmetic ops containing only atoms
        if all([sexp_type(o) == 'number' for o in [lop, rop]]):
            return ExplOps.binary_arith[op](lop, rop)
        elif op == '+' and all([sexp_type(o) == 'string' for o in [lop, rop]]):
            return lop + rop

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
    def handle_binary_logic_ops(self, op, ltype, rtype):
        if not all([t == 'boolean' for t in [ltype, rtype]]):
            raise ValueError(f"expected boolean operands in {(op, ltype, rtype)}")

        return 'boolean'

    @Lisp.handle(ExplOps.relation)
    def handle_relation_ops(self, op, ltype, rtype):
        if ltype != rtype:
            raise ValueError(f"data types are not equal in {(op, ltype, rtype)}")

        return 'boolean'

    @Lisp.handle(ExplOps.binary_arith)
    def handle_binary_arith_ops(self, op, ltype, rtype):
        if not all([t == 'number' for t in [ltype, rtype]]):
            raise ValueError(f"{(op, ltype, rtype)} contains an unexpected type")

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

        if op in ExplOps.inequation:
            if not (lit_type == sym_type == enum.typ == 'number'):
                raise ValueError(f"inequation with enum type can only be resolved with numbers")

            ineq = ExplOps.inequation[op]
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
