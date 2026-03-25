from __future__ import annotations

import random

from ..contracts import ProblemPayload

QUESTION_BANK_BY_TOPIC: dict[str, list[ProblemPayload]] = {
    "Algebra": [
        ProblemPayload(problem_id="q_linear_equation", raw_text="Solve for x: 3x - 7 = 20."),
        ProblemPayload(problem_id="q_system_equations", raw_text="Solve the system of equations: 2x + y = 11 and x - y = 1."),
        ProblemPayload(problem_id="q_quadratic", raw_text="Solve the quadratic equation x^2 - 5x + 6 = 0."),
        ProblemPayload(problem_id="q_factor_equation", raw_text="Solve for x: x^2 - 9x + 20 = 0."),
    ],
    "Geometry": [
        ProblemPayload(problem_id="q_triangle_heron", raw_text="A triangle has side lengths 13 cm, 14 cm, and 15 cm. Find its area."),
        ProblemPayload(problem_id="q_triangle_base_height", raw_text="A triangle has base 12 cm and height 9 cm. Find its area."),
        ProblemPayload(problem_id="q_circle_diameter", raw_text="A circle has diameter 14 cm. Find its area in terms of pi."),
        ProblemPayload(problem_id="q_angle_sum", raw_text="Two angles of a triangle are 48 degrees and 67 degrees. Find the third angle."),
    ],
    "Coordinate Geometry": [
        ProblemPayload(problem_id="q_midpoint", raw_text="Find the midpoint of the line segment joining (2, 5) and (8, 11)."),
        ProblemPayload(problem_id="q_distance", raw_text="Find the distance between the points (1, 2) and (7, 10)."),
        ProblemPayload(problem_id="q_slope", raw_text="Find the slope of the line passing through the points (-3, 4) and (5, 12)."),
    ],
    "Mensuration": [
        ProblemPayload(problem_id="q_rectangle_area", raw_text="A rectangle has length 18 cm and width 7 cm. Find its area."),
        ProblemPayload(problem_id="q_cylinder_volume", raw_text="A cylinder has radius 3 cm and height 10 cm. Find its volume in terms of pi."),
        ProblemPayload(problem_id="q_cube_surface_area", raw_text="A cube has side length 6 cm. Find its total surface area."),
    ],
    "Trigonometry": [
        ProblemPayload(problem_id="q_trig_ratio", raw_text="In a right triangle, the side opposite angle theta is 8 cm and the hypotenuse is 10 cm. Find sin(theta)."),
        ProblemPayload(problem_id="q_tangent_ratio", raw_text="In a right triangle, the side opposite angle A is 12 cm and the adjacent side is 5 cm. Find tan(A)."),
        ProblemPayload(problem_id="q_pythagorean_trig", raw_text="If sin(theta) = 3/5 and theta is acute, find cos(theta)."),
    ],
    "Calculus": [
        ProblemPayload(problem_id="q_derivative_power", raw_text="Differentiate y = 4x^3 - 5x^2 + 2x - 9 with respect to x."),
        ProblemPayload(problem_id="q_integral_poly", raw_text="Integrate with respect to x: 6x^2 + 4x + 1."),
        ProblemPayload(problem_id="q_limit_basic", raw_text="Evaluate the limit as x approaches 2 of x^2 + 3x - 1."),
    ],
    "Probability": [
        ProblemPayload(problem_id="q_probability_balls", raw_text="A bag contains 3 red balls and 5 blue balls. One ball is selected at random. What is the probability of drawing a red ball?"),
        ProblemPayload(problem_id="q_probability_coin", raw_text="Two fair coins are tossed. What is the probability of getting exactly one head?"),
        ProblemPayload(problem_id="q_probability_die", raw_text="A fair die is rolled once. What is the probability of getting a number greater than 4?"),
    ],
    "Statistics": [
        ProblemPayload(problem_id="q_average", raw_text="The scores 12, 15, 18, 20, and 25 are recorded. Find the mean score."),
        ProblemPayload(problem_id="q_median", raw_text="Find the median of the numbers 4, 7, 9, 10, 13, 15, and 18."),
        ProblemPayload(problem_id="q_mode", raw_text="Find the mode of the numbers 2, 5, 5, 7, 8, 5, 9, and 7."),
    ],
    "Number Theory": [
        ProblemPayload(problem_id="q_gcd", raw_text="Find the greatest common divisor of 48 and 72."),
        ProblemPayload(problem_id="q_lcm", raw_text="Find the least common multiple of 12 and 18."),
        ProblemPayload(problem_id="q_remainder", raw_text="What remainder is obtained when 125 is divided by 7?"),
    ],
    "Arithmetic": [
        ProblemPayload(problem_id="q_percentage", raw_text="What is 15% of 240?"),
        ProblemPayload(problem_id="q_ratio", raw_text="The ratio of boys to girls in a class is 3:5. If there are 40 students in total, how many are girls?"),
        ProblemPayload(problem_id="q_simple_interest", raw_text="Find the simple interest on Rs. 2000 at 5% per annum for 3 years."),
        ProblemPayload(problem_id="q_speed_distance", raw_text="A car travels 150 km in 3 hours. What is its average speed?"),
    ],
    "Combinatorics": [
        ProblemPayload(problem_id="q_combination", raw_text="How many ways can 3 students be chosen from a group of 8 students?"),
        ProblemPayload(problem_id="q_permutation", raw_text="How many different arrangements can be made using the letters of the word CAT?"),
        ProblemPayload(problem_id="q_counting", raw_text="How many two-digit numbers can be formed using the digits 1, 2, 3, and 4 without repetition?"),
    ],
    "Linear Algebra": [
        ProblemPayload(problem_id="q_matrix_addition", raw_text="Add the matrices [[2, 1], [3, 4]] and [[5, 0], [1, 2]]."),
        ProblemPayload(problem_id="q_determinant", raw_text="Find the determinant of the matrix [[4, 2], [1, 3]]."),
        ProblemPayload(problem_id="q_vector_magnitude", raw_text="Find the magnitude of the vector (6, 8)."),
    ],
}

QUESTION_BANK: list[ProblemPayload] = [
    problem.model_copy(deep=True)
    for topic_bank in QUESTION_BANK_BY_TOPIC.values()
    for problem in topic_bank
]


def get_problem_payload_for_topic(topic: str | None) -> ProblemPayload:
    if not topic:
        return get_random_problem_payload()

    topic_bank = QUESTION_BANK_BY_TOPIC.get(topic)
    if not topic_bank:
        return get_random_problem_payload()

    selected = random.choice(topic_bank)
    return selected.model_copy(deep=True)


def get_random_problem_payload() -> ProblemPayload:
    selected = random.choice(QUESTION_BANK)
    return selected.model_copy(deep=True)
