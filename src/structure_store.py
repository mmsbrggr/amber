"""
This modules contains functions providing the structures of a given monomial.
That means, given a monomial over the program variables (EVAR), the structures is all possible
branches only containing variables from the previous iteration.

Example:
while true:
    x = x - 1 @ 1/2; x + 1
    y = y - 1 @ 1/2; y + 1

Structures of x*y:
- (x - 1)(y - 1) @ 1/4
- (x + 1)(y - 1) @ 1/4
- (x - 1)(y + 1) @ 1/4
- (x + 1)(y + 1) @ 1/4

The structure of EVARs are computed just in time and stored so they can be reused.
"""

from diofant import *
from mora.core import Program
from .expression import get_branches_for_expression, get_initial_value_for_expression


class Structure:
    """
    The class actually representing a structure of an EVAR. It represents:
    EVAR_n = recurrence_constant * EVAR_{n - 1} + inhom_part_{n - 1} @ probability
    """
    evar: Expr
    recurrence_constant: Number
    inhom_part: Poly
    probability: Number
    initial_value: Number


store = {}
initial_value_store = {}
program = None


def set_program(p: Program):
    """
    Set the program and initialize the store. This function needs to be called before the store is used.
    """
    global program, store, initial_value_store
    program = p
    store = {}
    initial_value_store = {}


def get_structures_of_evar(evar) -> [Structure]:
    """
    Lazily computes the structures of a given EVAR and returns them.
    """
    evar = sympify(evar)
    if evar not in store:
        __compute_structures(evar)
    return store[evar]


def get_initial_value_of_evar(evar) -> Number:
    """
    Lazily computes the initial value of a given EVAR and returns them.
    """
    global program, initial_value_store
    evar = sympify(evar)
    if evar not in initial_value_store:
        initial_value_store[evar] = get_initial_value_for_expression(evar, program)
    return initial_value_store[evar]


def __compute_structures(evar):
    global program
    evar = sympify(evar)
    branches = get_branches_for_expression(evar, program)
    structures = __branches_to_structures(branches, evar)
    store[evar] = structures


def __branches_to_structures(branches, evar):
    result = []
    for branch in branches:
        structure = Structure()
        structure.evar = evar
        structure.recurrence_constant = branch[0].coeff_monomial(evar)
        structure.inhom_part = branch[0] - (structure.recurrence_constant * evar)
        structure.probability = branch[1]
        result.append(structure)
    return result
