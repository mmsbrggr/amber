from diofant import Symbol, sympify, simplify, expand, Expr, Poly, symbols, summation
from mora.utils import *
from typing import List, Dict, Set


class Program:
    def __init__(self):
        self.name: str = ""
        self.source: str = ""
        self.loop_guard: str = ""
        self.variables: List[Symbol] = []
        self.initial_values: Dict[Symbol, Update] = {}
        self.updates: Dict[Symbol, Update] = {}
        self.ancestors: Dict[Symbol, Set[Symbol]] = {}
        self.dependencies: Dict[Symbol, Set[Symbol]] = {}


# Stores the solutions of E-variables
solution_store = {}

# Stores the recurrences of E-variables
recurrence_store = {}


def reset_mora():
    global solution_store, recurrence_store
    solution_store = {}
    recurrence_store = {}


def core(program: Program, goal_monomials: List[Expr] = None, goal_power: int = 1):
    """
    Returns the expected values of given monomials raised to a given power. If no monomials are given the expected
    values of all program variables get computed.
    """
    global solution_store, recurrence_store
    reset_mora()
    if goal_monomials is None:
        goal_monomials = [v**goal_power for v in program.variables]

    goal_monomials = [m.as_poly(program.variables) for m in goal_monomials]
    solutions = {}
    for m in goal_monomials:
        solutions[m] = get_solution(program, m)
    return solution_store


def get_solution(program: Program, monomial: Poly):
    """
    For a given monomial returns its expected value by first checking if it already has been computed and stored
    """
    log(f"Start get solution, { monomial.as_expr() }", LOG_VERBOSE)
    global solution_store
    if monomial_is_constant(monomial):
        return monomial.as_expr()
    if monomial.as_expr() not in solution_store:
        solution_store[monomial.as_expr()] = compute_solution(program, monomial)
    log(f"End get solution, { monomial.as_expr() }", LOG_VERBOSE)
    return solution_store[monomial.as_expr()]


def compute_solution(program: Program, monomial: Poly):
    """
    For a given monomial returns its expected value by constructing and solving a recurrence relation
    """
    log(f"Start compute solution, { monomial.as_expr() }", LOG_VERBOSE)
    if monomial_is_constant(monomial):
        return monomial.as_expr()

    factor = monomial.coeffs()[0]
    monomial = monomial.monic()
    recurrence = get_recurrence(program, monomial)
    recurr_coeff = recurrence.coeff_monomial(monomial.as_expr())
    inhom_part = recurrence - (recurr_coeff * monomial)
    inhom_part_solution = get_inhom_part_solution(program, inhom_part)
    initial_value = get_expected_initial_value(program, monomial)
    solution = compute_solution_for_recurrence(recurr_coeff, inhom_part_solution, initial_value)
    log(f"End compute solution, { monomial.as_expr() }", LOG_ESSENTIAL)
    return factor * solution


def get_inhom_part_solution(program: Program, inhom_part: Poly):
    """
    For a given inhomogenous part of the assignment of a monomial replace the monomials in the inhom part by their
    closed form solutions.
    """
    log(f"Start get inhom_part_solution, { inhom_part.as_expr() }", LOG_VERBOSE)
    monomials = get_monoms(inhom_part)
    result = inhom_part.coeff_monomial(1)
    for monomial in monomials:
        solution = get_solution(program, monomial)
        monomial = monomial.as_expr()
        result += inhom_part.coeff_monomial(monomial) * solution
    log(f"End get inhom_part_solution, {inhom_part.as_expr()}", LOG_VERBOSE)
    return expand(result)


def get_expected_initial_value(program: Program, monomial: Poly):
    """
    For a given monomial computes the expected initial value
    """
    log(f"Start get expected initial value, { monomial.as_expr() }", LOG_VERBOSE)
    powers = monomial.monoms()[0]
    vars_with_powers = [(var, power) for var, power in zip(monomial.gens, powers)]
    result = sympify(1)
    for variable, power in vars_with_powers:
        if power > 0 and variable in program.initial_values:
            if program.initial_values[variable].is_random_var:
                # Variable initialized with RV
                result *= program.initial_values[variable].random_var.compute_moment(power)
            else:
                # Variable initialized with branches
                result *= sum([b[1] * (b[0]**power) for b in program.initial_values[variable].branches])
    log(f"End get expected initial value, { monomial.as_expr() }", LOG_VERBOSE)
    return result


def compute_solution_for_recurrence(recurr_coeff: Expr, inhom_part_solution: Expr, initial_value: Expr):
    """
    Computes the (unique) solution to the recurrence relation:
    f(0) = initial_value; f(n+1) = recurr_coeff * f(n) + inhom_part_solution
    """
    log(f"Start compute solution for recurrence, { recurr_coeff }, { inhom_part_solution }, { initial_value }", LOG_VERBOSE)
    n = symbols('n', integer=True, positive=True)
    if recurr_coeff.is_zero:
        return expand(inhom_part_solution.xreplace({n: n-1}))

    hom_solution = (recurr_coeff ** n) * initial_value
    k = symbols('_k', integer=True, positive=True)
    summand = simplify((recurr_coeff ** k) * inhom_part_solution.xreplace({n: (n-1) - k}))
    particular_solution = summation(summand, (k, 0, (n-1)))
    particular_solution = without_piecewise(particular_solution)
    solution = simplify(hom_solution + particular_solution)
    log(f"End compute solution for recurrence, { recurr_coeff }, { inhom_part_solution }, { initial_value }", LOG_VERBOSE)
    return solution


def get_recurrence(program: Program, monomial: Poly):
    """
    For a given monomial returns its recurrence representation by first checking if it already
    as been computed and stored
    """
    log(f"Start get recurrence, { monomial.as_expr() }", LOG_VERBOSE)
    global recurrence_store
    if monomial_is_constant(monomial):
        return monomial
    if monomial.as_expr() not in recurrence_store:
        recurrence_store[monomial.as_expr()] = compute_recurrence(program, monomial)
    log(f"End get recurrence, { monomial.as_expr() }", LOG_VERBOSE)
    return recurrence_store[monomial.as_expr()]


def compute_recurrence(program: Program, monomial: Poly):
    """
    Iteratively splits a monomial on variables which are dependent with respect to the given monomial
    """
    log(f"Start compute recurrence, { monomial.as_expr() }", LOG_VERBOSE)
    result = monomial.as_expr()
    split_variables = set()
    for variable, update in reversed(program.updates.items()):
        if variable not in result.free_symbols:
            continue

        if update.is_random_var:
            result = replace_rv_in_polynomial(program, result.as_poly(program.variables), variable).as_expr()
            continue

        split_variables.add(variable)
        branches = split_expression_on_variable(program, result, variable)
        log(f"Start combining {len(branches)} branches", LOG_VERBOSE)
        result = sum([prob * branch for branch, prob in branches])
        log(f"Mid combining branches", LOG_VERBOSE)
        result = expand(result)
        log(f"End combining branches", LOG_VERBOSE)

    log(f"End compute recurrence, { monomial.as_expr() }", LOG_VERBOSE)
    return result.as_poly(program.variables)


def split_expression_on_variable(program: Program, expression, variable):
    """
    For a given expression, splits it with the updates of a given variable.
    """
    log(f"Start split expression on variable, { variable }", LOG_VERBOSE)
    if variable not in expression.free_symbols:
        return [(expression, sympify(1))]

    branches = []
    for b, p in program.updates[variable].branches:
        branches.append((expression.xreplace({variable: b}), p))
    log(f"End split expression on variable, { variable }", LOG_VERBOSE)
    return branches


def replace_rv_in_polynomial(program: Program, polynomial: Poly, rv: Symbol):
    """
    For a given polynomial return a polynomial such that all powers of a random variable are replaced with their
    corresponding moments.
    """
    log(f"Start replace rv in polynomial, { rv }", LOG_VERBOSE)
    powers = get_powers_of_variable_in_polynomial(rv, polynomial)
    replacements = {rv ** p: program.updates[rv].random_var.compute_moment(p) for p in powers}
    polynomial = polynomial.as_expr().xreplace(replacements).as_poly(program.variables)
    log(f"End replace rvs in polynomial, { rv }", LOG_VERBOSE)
    return polynomial
