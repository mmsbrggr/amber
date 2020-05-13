"""
This module contains functions which compute for for a given expression M_{i+1} all possible M_i
which could be the predecessor of M_{i+1} before executing the loop body together with the associated
probabilities.
"""

from diofant import Expr, Symbol, simplify, Rational, symbols, Number
from mora.core import Program

# Type aliases to improve readability
Probability = Rational
Case = (Expr, Probability)


def get_cases_for_expression(expression: Expr, program: Program) -> [Case]:
    """
    The main function computing all possible expression_{i+1} together with the associated probabilities
    """
    result = [(expression, 1)]

    for symbol in reversed(program.variables):
        result = split_expressions_on_symbol(result, symbol, program)
        result = combine_expressions(result)

    variables = set(program.variables).difference({symbols('n')})
    return to_polynomials(result, variables)


def get_initial_value_for_expression(expression: Expr, program: Program) -> Number:
    """
    For a given expression returns its initial value
    """
    result = expression.subs({symbols('n'): 0})
    for var, update in program.initial_values.items():
        if hasattr(update, 'branches') and len(update.branches) > 0:
            result = result.subs({var: update.branches[0][0]})
    return simplify(result)


def split_expressions_on_symbol(expressions: [Case], symbol: Symbol, program: Program):
    """
    Splits all given expressions on the possibilities of updating a given symbol
    """
    result = []
    for expr, prob in expressions:
        if symbol in program.updates.keys() and symbol in expr.free_symbols:
            for u, p in program.updates[symbol].branches:
                new_expression = simplify(expr.subs({symbol: u}))
                new_prob = prob * p
                result.append((new_expression, new_prob))
        else:
            result.append((expr, prob))

    return result


def combine_expressions(expressions: [Case]) -> [Case]:
    """
    In a given list of expressions with probabilities, combines equal expressions and their probabilities
    """
    tmp_map = {}
    for e, p in expressions:
        tmp_map[e] = tmp_map[e] + p if e in tmp_map else p
    return list(tmp_map.items())


def to_polynomials(expressions: [Case], variables) -> [Case]:
    """
    Converts all expressions in a list of cases to polynomials in the program variables
    """
    result = []
    for e, p in expressions:
        e = e.as_poly(variables)
        result.append((e, p))

    return result
