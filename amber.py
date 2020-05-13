"""This file is part of Amber

This runnable script allows the user to run Amber on probabilistic programs stored in files
For the command line arguments run the script with "--help".
"""

import glob
from argparse import ArgumentParser

from mora.mora import mora, MoraException
from src import decide_termination
from src.bounds import bounds


HEADER = """
    _    __  __  ___  ___  ___ 
   /_\  |  \/  || _ )| __|| _ \ 
  / _ \ | |\/| || _ \| _| |   / 
 /_/ \_\|_|  |_||___/|___||_|_\ 
"""


parser = ArgumentParser(description="Run Amber on probabilistic programs stored in files")

parser.add_argument(
    "--benchmarks",
    dest="benchmarks",
    required=True,
    type=str,
    nargs="+",
    help="A list of benchmarks to run Amber on"
)

parser.add_argument(
    "--bounds",
    dest="bounds",
    type=str,
    default="",
    help="This is just a development flag. If set, it calculates the asymptotic bounds of the given expression"
)


def main():
    print(HEADER)

    args = parser.parse_args()
    args.benchmarks = [b for bs in map(glob.glob, args.benchmarks) for b in bs]

    for benchmark in args.benchmarks:
        if args.bounds:
            bounds(benchmark, args.bounds)
        else:
            try:
                program = mora(benchmark, goal=1)
                decide_termination(program)
            except MoraException as exception:
                print("Something went wrong with Mora", exception)


if __name__ == "__main__":
    main()
