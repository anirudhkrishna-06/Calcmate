from __future__ import annotations

import random

from ..contracts import ProblemPayload

QUESTION_BANK: list[ProblemPayload] = [
    ProblemPayload(problem_id="q_triangle_heron", raw_text="A triangle has side lengths 13 cm, 14 cm, and 15 cm. Find its area."),
    ProblemPayload(problem_id="q_triangle_base_height", raw_text="A triangle has base 12 cm and height 9 cm. Find its area."),
    ProblemPayload(problem_id="q_circle_diameter", raw_text="A circle has diameter 14 cm. Find its area in terms of pi."),
    ProblemPayload(problem_id="q_rectangle_area", raw_text="A rectangle has length 18 cm and width 7 cm. Find its area."),
    ProblemPayload(problem_id="q_linear_equation", raw_text="Solve for x: 3x - 7 = 20."),
    ProblemPayload(problem_id="q_system_equations", raw_text="Solve the system of equations: 2x + y = 11 and x - y = 1."),
    ProblemPayload(problem_id="q_quadratic", raw_text="Solve the quadratic equation x^2 - 5x + 6 = 0."),
    ProblemPayload(problem_id="q_percentage", raw_text="What is 15% of 240?"),
    ProblemPayload(problem_id="q_ratio", raw_text="The ratio of boys to girls in a class is 3:5. If there are 40 students in total, how many are girls?"),
    ProblemPayload(problem_id="q_speed_distance", raw_text="A car travels 150 km in 3 hours. What is its average speed?"),
    ProblemPayload(problem_id="q_probability", raw_text="A bag contains 3 red balls and 5 blue balls. One ball is selected at random. What is the probability of drawing a red ball?"),
    ProblemPayload(problem_id="q_average", raw_text="The scores 12, 15, 18, 20, and 25 are recorded. Find the mean score."),
    ProblemPayload(problem_id="q_simple_interest", raw_text="Find the simple interest on Rs. 2000 at 5% per annum for 3 years."),
]


def get_random_problem_payload() -> ProblemPayload:
    selected = random.choice(QUESTION_BANK)
    return selected.model_copy(deep=True)
