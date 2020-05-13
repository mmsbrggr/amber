"""
This modules contains functions providing the bounds of given evars and polynomial of evars.
"""

from diofant import *
from mora.core import Program
from .utils import *
from .asymptotics import *
from . import structure_store

store = {}
program = None


class Bounds:
    expression: Poly
    lower: Expr
    upper: Expr
    maybe_positive: bool
    maybe_negative: bool
    __absolute_upper__: Expr = None

    @property
    def absolute_upper(self):
        if self.__absolute_upper__ is None:
            n = symbols('n')
            self.__absolute_upper__ = get_eventual_bound([self.upper, self.lower * -1], n)
        return self.__absolute_upper__


def set_program(p: Program):
    """
    Set the program and initialize the store. This function needs to be called before the store is used.
    """
    global program, store
    program = p
    store = {}


def get_bounds_of_expr(expression: Expr) -> Bounds:
    """
    Computes the bounds of a polynomial over the program variables. It does so by substituting the bounds of the evars.
    """
    expression = sympify(expression)
    variables = set(program.variables).difference({symbols('n')})
    expression = expression.as_poly(variables)
    expr_bounds = __initialize_bounds_for_expression(expression)
    evars = get_monoms(expression)
    for evar in evars:
        evar_bounds = __get_bounds_of_evar(evar)
        __replace_evar_in_expr_bounds(evar, evar_bounds, expression, expr_bounds)

    upper_candidates = __split_on_signums(expr_bounds.upper.as_expr())
    lower_candidates = __split_on_signums(expr_bounds.lower.as_expr())

    expr_bounds.upper = get_eventual_bound(upper_candidates, symbols('n'), direction=Direction.PosInf)
    expr_bounds.lower = get_eventual_bound(lower_candidates, symbols('n'), direction=Direction.NegInf)
    return expr_bounds


def __replace_evar_in_expr_bounds(evar, evar_bounds: Bounds, expression: Poly, expr_bounds: Bounds):
    """
    Helper function which replaces a single evar with its bounds. Which bound to take depends on the coefficient
    of the evar.
    """
    coeff = expression.coeff_monomial(evar)
    if coeff > 0:
        upper = evar_bounds.upper
        lower = evar_bounds.lower
        pos = evar_bounds.maybe_positive
        neg = evar_bounds.maybe_negative
    else:
        upper = evar_bounds.lower
        lower = evar_bounds.upper
        pos = evar_bounds.maybe_negative
        neg = evar_bounds.maybe_positive

    expr_bounds.upper = expr_bounds.upper.subs({evar: upper})
    expr_bounds.lower = expr_bounds.lower.subs({evar: lower})
    # Rough estimate of whether the expression is positive/negative
    expr_bounds.maybe_positive = expr_bounds.maybe_positive or pos
    expr_bounds.maybe_negative = expr_bounds.maybe_negative or neg


def __initialize_bounds_for_expression(expression: Poly) -> Bounds:
    """
    Initializes the bounds object for an expression by setting the lower and upper bounds equal to the expression.
    """
    bounds = Bounds()
    bounds.expression = expression.as_expr()
    bounds.lower = expression.copy()
    bounds.upper = expression.copy()

    # Initialize the polarity of the expression by the polarity of the deterministic part
    n_expr = expression.coeff_monomial(1)
    pos, neg = get_polarity(n_expr, symbols('n'))

    bounds.maybe_positive = pos
    bounds.maybe_negative = neg
    return bounds


def __get_bounds_of_evar(evar: Expr) -> Bounds:
    """
    Computes the bounds of an evar in a lazy way
    """
    evar = sympify(evar).as_expr()
    if evar not in store:
        __compute_bounds_of_evar(evar)
    return store[evar]


def __compute_bounds_of_evar(evar: Expr):
    print(f"Computing bounds for {evar.as_expr()}")
    if len(evar.free_symbols) == 1 and get_all_evar_powers(evar)[0] > 2:
        variable = evar.free_symbols.pop()
        power = get_all_evar_powers(evar)[0]
        if power % 2 == 0:
            evar = variable ** 2
            power = int(power / 2)
        else:
            evar = variable
            power = power
        __compute_bounds_of_evar_power(evar, power)
    else:
        __compute_bounds_of_evar_structure(evar)
    print(f"Found bounds for {evar.as_expr()}")


def __compute_bounds_of_evar_power(evar: Expr, power: Number):
    """
    Computes the bounds of evar**odd_power by just taking the bounds of evar and raising it to the given power.
    This is only sound if the given power is odd or the evar is always positive
    """
    n = symbols('n')
    evar_bounds = __get_bounds_of_evar(evar)
    upper_bound = simplify_asymptotically(evar_bounds.upper ** power, n)
    lower_bound = simplify_asymptotically(evar_bounds.lower ** power, n)

    bounds = Bounds()
    bounds.expression = (evar ** power).as_expr()
    bounds.upper = upper_bound
    bounds.lower = lower_bound
    bounds.maybe_positive = evar_bounds.maybe_positive
    bounds.maybe_negative = evar_bounds.maybe_negative

    store[bounds.expression] = bounds


def __compute_bounds_of_evar_structure(evar: Expr):
    """
    Computes the bounds of an evar by representing it as a recurrence relation
    """
    n = symbols('n')
    structures = structure_store.get_structures_of_evar(evar)
    inhom_parts_bounds = [get_bounds_of_expr(s.inhom_part) for s in structures]
    initial_value = structure_store.get_initial_value_of_evar(evar)
    maybe_pos, maybe_neg = __get_evar_polarity(evar, inhom_parts_bounds, initial_value)

    inhom_parts_bounds_lower = [b.lower.subs({n: n - 1}) for b in inhom_parts_bounds]
    inhom_parts_bounds_upper = [b.upper.subs({n: n - 1}) for b in inhom_parts_bounds]

    max_upper = get_eventual_bound(inhom_parts_bounds_upper, n, direction=Direction.PosInf)
    min_lower = get_eventual_bound(inhom_parts_bounds_lower, n, direction=Direction.NegInf)
    min_rec = min([s.recurrence_constant for s in structures])
    max_rec = max([s.recurrence_constant for s in structures])
    starting_values = __get_starting_values(maybe_pos, maybe_neg)

    upper_candidates = __compute_bound_candidates({min_rec, max_rec}, {max_upper}, starting_values)
    lower_candidates = __compute_bound_candidates({min_rec, max_rec}, {min_lower}, starting_values)

    max_upper_candidate = get_eventual_bound(upper_candidates, n, direction=Direction.PosInf)
    min_lower_candidate = get_eventual_bound(lower_candidates, n, direction=Direction.NegInf)

    # If evar is negative upper bound cannot be larger than 0
    if not maybe_pos:
        max_upper_candidate = get_eventual_bound([max_upper_candidate, sympify(0)], n, direction=Direction.NegInf)
    # If evar is positive lower bound cannot be smaller than 0
    if not maybe_neg:
        min_lower_candidate = get_eventual_bound([min_lower_candidate, sympify(0)], n, direction=Direction.PosInf)

    bounds = Bounds()
    bounds.expression = evar.as_expr()
    bounds.upper = max_upper_candidate.as_expr()
    bounds.lower = min_lower_candidate.as_expr()
    bounds.maybe_positive = maybe_pos
    bounds.maybe_negative = maybe_neg

    store[bounds.expression] = bounds


def __get_evar_polarity(evar: Expr, inhom_parts_bounds: [Bounds], initial_value: Number) -> (bool, bool):
    """
    Returns a rough but sound estimate of whether or not a given evar can be positive and negative
    """
    # If all powers of the variables are even, the evar is only positive
    powers = get_all_evar_powers(evar)
    all_powers_even = all([p % 2 == 0 for p in powers])
    if all_powers_even:
        return True, False

    # Otherwise estimate evar polarity by polarity of initial condition and polarity of inhomogenous parts
    initial_pos = sympify(initial_value) > 0
    if initial_pos.is_Relational:
        initial_pos = True
    else:
        initial_pos = bool(initial_pos)

    initial_neg = sympify(initial_value) < 0
    if initial_neg.is_Relational:
        initial_neg = True
    else:
        initial_neg = bool(initial_neg)

    maybe_pos = initial_pos or any([b.maybe_positive for b in inhom_parts_bounds])
    maybe_neg = initial_neg or any([b.maybe_negative for b in inhom_parts_bounds])
    return maybe_pos, maybe_neg


def __get_starting_values(maybe_pos: bool, maybe_neg: bool) -> [Expr]:
    """
    Returns the possible values of an evar after which an evar is within a certain bound. This gets used
    to solve the recurrence relations for the bounds candidates.
    """
    values = []
    if maybe_pos:
        values.append(unique_symbol('d', positive=True, real=True))
    if maybe_neg:
        values.append(unique_symbol('d', positive=True, real=True) * -1)
    if not maybe_pos and not maybe_neg:
        values.append(sympify(0))

    return values


def __compute_bound_candidates(coefficients: [Number], inhom_parts: [Expr], starting_values: [Expr]) -> [Expr]:
    """
    Computes functions which could potentially be bounds
    """
    candidates = []

    for c in coefficients:
        for part in inhom_parts:
            c0 = symbols('c0')
            solution = __compute_bound_candidate(c, part, c0)
            for v in starting_values:
                solution = solution.subs({c0: v})
                # If a candidate contains signum functions, we have to split the candidate into more candidates
                new_candidates = __split_on_signums(solution)
                candidates += new_candidates

    return candidates


def __compute_bound_candidate(c: Number, inhom_part: Expr, starting_value: Expr) -> Expr:
    """
    Computes a single function which is potentially a bound be solving a recurrence relation
    """
    f = Function('f')
    n = symbols('n')
    solution = rsolve(f(n) - c*f(n-1) - inhom_part, f(n), {f(0): starting_value})
    return solution


def __split_on_signums(expression: Expr) -> [Expr]:
    """
    For a given expression returns all expression resulting from splitting it on signum functions occurring in
    its limit, e.g. for c*sign(d - 1) returns [c*e, c*(-e)]
    """
    exps = [expression]
    n = symbols('n')
    expression_limit = limit(expression, n, oo)
    signums = get_signums_in_expression(expression_limit)
    for s in signums:
        # Choose an arbitrary symbol from the signum expression
        assert len(s.free_symbols) >= 1
        symbol = list(s.free_symbols)[0]
        new_exps = []
        for exp in exps:
            # Get rid of the signum expression by replacing it by a positve and an negative constant
            # This is done by substituting the arbitrary symbol by just the right expression s.t. things cancel out
            constant = unique_symbol('e', positive=True, real=True)
            solutions = solve(s - constant, [symbol])
            assert len(solutions) >= 1
            solution_pos = solutions[0][symbol]
            solution_neg = solution_pos.subs({constant: constant * -1})
            new_exps.append(exp.subs({symbol: solution_pos}))
            new_exps.append(exp.subs({symbol: solution_neg}))
        exps = new_exps
    return exps
