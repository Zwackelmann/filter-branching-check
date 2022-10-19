from fbc.lisp.core import Lisp, is_atom, is_enum_sexp, sexp_like, sexp_type
from fbc.algebra.core import ExplOps, Enum
from collections import defaultdict
from functools import reduce


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

    @Lisp.handle(['in', 'nin'], leafs=Lisp.ALL)
    def handle_enum(self, *_):
        return 'boolean'

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

    @Lisp.handle({**ExplOps.inequation, **ExplOps.equal}, default=Lisp.NOOP)
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
            ineq = ops[op]
            valid_lit = {e for e in enum if ineq(e, lit)}
            return 'in', enum, valid_lit
        elif op == '==':
            if lit not in enum:
                raise ValueError(f"{sym_name} must be one of {enum}. Found {lit}")

            return 'in', enum, {lit}
        else:
            raise ValueError(f"unexpected operator: ${op}")

    @Lisp.handle('symbol', leafs=Lisp.ALL)
    def handle_symbol(self, *_):
        return Lisp.NOOP


class Simplify(Lisp):
    @Lisp.handle("not")
    def handle_not(self, _, term):
        if sexp_type(term) == "not":
            return term[1]
        elif sexp_type(term) == "and":
            return ("or", ) + tuple([Simplify.eval(('not', t)) for t in term[1:]])
        elif sexp_type(term) == "or":
            return ("and", ) + tuple([Simplify.eval(('not', t)) for t in term[1:]])
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
        elif sexp_type(term) == 'in':
            return 'nin', term[1], term[2]
        elif sexp_type(term) == 'nin':
            return 'in', term[1], term[2]
        elif type(term) == bool:
            return not term
        elif sexp_type(term) == 'symbol' or is_atom(term):
            return Lisp.NOOP
        else:
            raise ValueError("")

    @Lisp.handle({**ExplOps.binary_arith, **ExplOps.binary_logic})
    def handle_transitive_binary(self, op, *terms):
        res = []
        for term in terms:
            if sexp_type(term) == op:
                res.extend(term[1:])
            else:
                res.append(term)

        if op == 'and':
            res = self.simplify_and(res)
        elif op == 'or':
            res = self.simplify_or(res)

        if len(res) == 0:
            raise ValueError()
        elif len(res) == 1:
            return res[0]
        else:
            return (op, ) + tuple(res)

    @Lisp.handle('nin', leafs=Lisp.ALL)
    def handle_nin(self, _, sym, lset):
        if isinstance(sym, Enum):
            return 'in', sym, sym.members.difference(lset)
        else:
            return 'nin', sym, lset

    @Lisp.handle(['symbol', 'in'], leafs=Lisp.ALL)
    def ignore(self, *_):
        return Lisp.NOOP

    def simplify_and(self, terms):
        ins = {}
        nins = {}
        out_terms = []
        for term in terms:
            if sexp_type(term) == 'in':
                _, sym, lset = term
                if sym in ins:
                    ins[sym] = ins[sym].intersection(lset)
                else:
                    ins[sym] = lset
            elif sexp_type(term) == 'nin':
                _, sym, lset = term
                if sym in nins:
                    nins[sym] = nins[sym].union(lset)
                else:
                    nins[sym] = lset
            else:
                out_terms.append(term)

        for sym in set(ins.keys()).union(nins.keys()):
            if sym not in ins and sym in nins:
                out_terms.append(self.handle_nin(('nin', sym, nins[sym])))
            else:
                in_set = ins.get(sym, set())
                nin_set = nins.get(sym, set())

                in_set = in_set.difference(nin_set)

                if len(in_set) >= 1:
                    out_terms.append(('in', sym, in_set))
                else:
                    out_terms.append(False)
        return out_terms

    def simplify_or(self, terms):
        ins = {}
        nins = {}
        out_terms = []
        for term in terms:
            if sexp_type(term) == 'in':
                _, sym, lset = term
                if sym in ins:
                    ins[sym] = ins[sym].union(lset)
                else:
                    ins[sym] = lset
            elif sexp_type(term) == 'nin':
                _, sym, lset = term
                if sym in nins:
                    nins[sym] = nins[sym].intersection(lset)
                else:
                    nins[sym] = lset
            else:
                out_terms.append(term)

        for sym in set(ins.keys()).union(nins.keys()):
            if sym in ins and sym not in nins:
                out_terms.append(('in', sym, ins[sym]))
            else:
                in_set = ins.get(sym, set())
                nin_set = nins.get(sym, set())

                nin_set = nin_set.difference(in_set)
                if len(nin_set) >= 1:
                    out_terms.append(self.handle_nin(('nin', sym, nin_set)))
                else:
                    out_terms.append(True)

        return out_terms
