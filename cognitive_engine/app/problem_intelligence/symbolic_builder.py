from __future__ import annotations

import re
from typing import Iterable

from ..contracts import MethodDefinition

TOKEN_PATTERN = re.compile(r"[A-Za-z_]+|\d+(?:\.\d+)?|[=+\-*/^()]")


def _tokenize(expression: str) -> list[str]:
    return TOKEN_PATTERN.findall(expression)


def _wl_subtrees(equations: Iterable[str]) -> list[list[str]]:
    subtrees: list[list[str]] = []
    for equation in equations:
        tokens = _tokenize(equation)
        if not tokens:
            continue
        width_two = [" ".join(tokens[index:index + 2]) for index in range(max(0, len(tokens) - 1))]
        width_three = [" ".join(tokens[index:index + 3]) for index in range(max(0, len(tokens) - 2))]
        subtrees.append(tokens + width_two + width_three)
    return subtrees


def build_symbolic_representation(methods: list[MethodDefinition]) -> tuple[list[str], list[list[str]]]:
    equations: list[str] = []
    for method in methods:
        equations.extend(method.equations)
    unique_equations = list(dict.fromkeys(equations))
    return unique_equations, _wl_subtrees(unique_equations)
