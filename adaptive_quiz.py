# =============================================================================
#  ADAPTIVE PRACTICE FORUM (REINFORCEMENT AGENT LAYER) - WITH DATASET INTEGRATION
# =============================================================================

import random
import re
import csv
import io
import sys
import io
import re
from sympy import sympify, Eq, solve, symbols
import matplotlib.pyplot as plt

#Symbolic solver (Standalone version)

class SymbolicSolver:
    """
    Standalone version of your SymbolicSolver.
    Removes DSPy dependency but keeps your powerful cleaning & solving logic.
    """
    def _clean_equation_string(self, eq_str):
        """Clean equation string to make it SymPy-compatible (Exact logic from your main file)"""
        # 1. Remove commas immediately (Fixes 15,000 -> 15000)
        eq_str = eq_str.replace(',', '')

        # Remove units and common text
        eq_str = re.sub(r'\b(km/h|km|miles|mph|cm|m|kg|g|lbs|dollars|\$)\b', '', eq_str)
        
        # Fix implicit multiplication (e.g., 2x -> 2*x, xy -> x*y)
        eq_str = re.sub(r'(\d+)([a-zA-Z])', r'\1*\2', eq_str)  # 2x -> 2*x
        eq_str = re.sub(r'([a-zA-Z])(\d+)', r'\1*\2', eq_str)  # x2 -> x*2
        eq_str = re.sub(r'([a-zA-Z])([a-zA-Z])', r'\1*\2', eq_str)  # xy -> x*y
        
        # Fix common word problems
        eq_str = re.sub(r'\b(length|width|height|area|perimeter|speed|distance|time)\b', 
                        lambda m: m.group(1)[0], eq_str)  # length -> l, width -> w, etc.
        
        # Remove extra spaces and clean up
        eq_str = re.sub(r'\s+', ' ', eq_str).strip()
        
        # Handle specific patterns
        eq_str = eq_str.replace(' x ', ' * ')  # word "x" to multiplication
        eq_str = eq_str.replace('Area =', 'A =')
        eq_str = eq_str.replace('length x width', 'l * w')
        
        return eq_str

    def __call__(self, canonical_equations):
        """Mimics the 'forward' method but makes the class callable directly."""
        # Simple result object to replace dspy.Prediction
        class SolverResult:
            def __init__(self, success, solution):
                self.success = success
                self.solution = solution

        try:
            if not canonical_equations:
                return SolverResult(False, {})
            
            equations_to_solve = []
            for eq in canonical_equations:
                try:
                    # Clean up the equation string
                    cleaned_eq = self._clean_equation_string(eq)
                    
                    # First try to parse as equation (with =)
                    if '=' in cleaned_eq:
                        parts = cleaned_eq.split('=', 1)
                        if len(parts) == 2:
                            lhs = sympify(parts[0].strip())
                            rhs = sympify(parts[1].strip())
                            equations_to_solve.append(Eq(lhs, rhs))
                        else:
                            equations_to_solve.append(sympify(cleaned_eq))
                    else:
                        equations_to_solve.append(sympify(cleaned_eq))
                except:
                    continue
            
            if not equations_to_solve:
                return SolverResult(False, {})
            
            # Extract symbols
            syms = set()
            for e in equations_to_solve:
                if hasattr(e, 'free_symbols'):
                    syms.update(e.free_symbols)
            
            # Solve
            sol = solve(equations_to_solve, list(syms), dict=True)
            
            if not sol:
                # If no solution found, maybe it's a direct evaluation?
                # (Handle cases where user types just "50")
                return SolverResult(False, {})

            sol0 = sol[0]
            
            # Convert SymPy logic to simple Python types for the Grader
            clean_sol = {str(k): float(v) for k, v in sol0.items()}
            return SolverResult(True, clean_sol)

        except Exception as e:
            return SolverResult(False, {})
# Safer way to handle Emojis on Windows without crashing
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass # If reconfigure isn't available, just ignore it
# ---------------------------------------------------------
# 1. THE DATASET (Embedded for portability)
# ---------------------------------------------------------
RAW_DATASET = """problem_id,problem_text,solution_text
1,A car covers 150 km in 3 hours. What is its speed?,Speed = Distance / Time = 150 / 3 = 50 km/hr
2,The sum of two numbers is 40 and their difference is 10. Find the numbers.,"Let x + y = 40, x − y = 10 → x = 25, y = 15"
3,"If a book costs $12 and you buy 5 books, how much do you spend?",Total cost = 12 × 5 = $60
4,A rectangle has a length of 10 cm and width of 6 cm. What is its area?,Area = Length × Width = 10 × 6 = 60 cm²
5,"If 40% of a number is 80, what is the number?",Let x be the number: 0.4x = 80 → x = 200
6,A train travels at 60 km/h. How far does it travel in 2.5 hours?,Distance = Speed × Time = 60 × 2.5 = 150 km
7,The perimeter of a square is 36 cm. What is the length of each side?,Perimeter = 4 × side → 36 = 4s → s = 9 cm
8,"If 3 pens cost $6, how much do 8 pens cost?",Cost per pen = 6/3 = $2 → 8 pens = 8 × 2 = $16
9,The sum of three consecutive numbers is 51. Find the numbers.,"Let x, x+1, x+2 be the numbers: x + (x+1) + (x+2) = 51 → x = 16. Numbers are 16, 17, 18"
10,A store offers a 25% discount on a $80 item. What is the sale price?,Discount = 0.25 × 80 = $20 → Sale price = 80 - 20 = $60
11,"If the ratio of boys to girls is 3:2 and there are 15 boys, how many girls are there?",3:2 = 15:x → 3x = 30 → x = 10 girls
12,A circle has a radius of 5 cm. What is its circumference? (Use π ≈ 3.14),Circumference = 2πr = 2 × 3.14 × 5 = 31.4 cm
13,"If a worker earns $15 per hour and works 40 hours a week, what is the weekly earnings?",Weekly earnings = 15 × 40 = $600
14,The area of a triangle is 30 cm² and its base is 10 cm. What is the height?,Area = (Base × Height)/2 → 30 = (10 × h)/2 → h = 6 cm
15,"If you have $500 and spend 30% of it, how much is left?",Amount spent = 0.3 × 500 = $150 → Amount left = 500 - 150 = $350
16,A recipe requires 2 cups of flour for 24 cookies. How much flour is needed for 36 cookies?,Proportion: 2/24 = x/36 → x = 3 cups
17,"If the average of 4 numbers is 25, what is their sum?",Sum = Average × Count = 25 × 4 = 100
18,A tank holds 500 liters and is 60% full. How many liters are in the tank?,Volume = 0.6 × 500 = 300 liters
19,"If x + 5 = 20, what is the value of x?",x = 20 - 5 = 15
20,The cost of 6 notebooks is $18. What is the cost of 10 notebooks?,Cost per notebook = 18/6 = $3 → 10 notebooks = 10 × 3 = $30
21,"If a car depreciates by 15% each year and costs $20,000 now, what will it cost after 1 year?","Depreciation = 0.15 × 20,000 = $3,000 → New price = 20,000 - 3,000 = $17,000"
22,"The sum of angles in a triangle is 180°. If two angles are 50° and 70°, what is the third angle?",Third angle = 180 - 50 - 70 = 60°
23,"If you invest $1,000 at 5% annual interest, how much interest will you earn in 1 year?","Interest = 0.05 × 1,000 = $50"
24,"A photo is 8 inches by 6 inches. If you enlarge it by a scale factor of 1.5, what are the new dimensions?","New length = 8 × 1.5 = 12 inches, New width = 6 × 1.5 = 9 inches"
25,"If the population of a city increases by 20% and was 100,000, what is the new population?","Increase = 0.2 × 100,000 = 20,000 → New population = 100,000 + 20,000 = 120,000"
26,"A student scored 85, 90, and 88 on three tests. What is the average score?",Average = (85 + 90 + 88)/3 = 263/3 ≈ 87.67
27,"If a recipe serves 4 people and uses 2 eggs, how many eggs are needed to serve 10 people?",Proportion: 2/4 = x/10 → x = 5 eggs
28,"The distance between two cities is 300 km. If a car travels at 75 km/h, how long does it take?",Time = Distance / Speed = 300 / 75 = 4 hours
29,"If the probability of an event is 0.25, what is the probability it does not occur?",P(not occurring) = 1 - 0.25 = 0.75
30,A store buys items for $50 and sells them for $80. What is the profit margin percentage?,Profit = 80 - 50 = $30 → Profit margin = (30/50) × 100 = 60%
31,"If 15% of a number is 45, what is 30% of that number?",Number = 45/0.15 = 300 → 30% of 300 = 0.3 × 300 = 90
32,A rectangular garden is 20 meters long and 15 meters wide. What is its perimeter?,Perimeter = 2(length + width) = 2(20 + 15) = 70 meters
33,"If a subscription costs $10 per month, how much does it cost for 2 years?",Cost = 10 × 12 × 2 = $240
34,The area of a square is 64 cm². What is its perimeter?,Side = √64 = 8 cm → Perimeter = 4 × 8 = 32 cm
35,"If you save $50 per week, how much will you save in 1 year?","Annual savings = 50 × 52 = $2,600"
36,"A ball is dropped from 100 meters. If it bounces to 80% of its previous height, how high is the first bounce?",First bounce height = 0.8 × 100 = 80 meters
37,"If the tax rate is 8% and an item costs $50, what is the total cost including tax?",Tax = 0.08 × 50 = $4 → Total = 50 + 4 = $54
38,"A class has 30 students. If 20% are absent, how many are present?",Absent = 0.2 × 30 = 6 → Present = 30 - 6 = 24
39,"If 2x + 3 = 13, what is the value of x?",2x = 13 - 3 = 10 → x = 5
40,"The ratio of apples to oranges in a basket is 5:3. If there are 15 apples, how many oranges are there?",5:3 = 15:x → 5x = 45 → x = 9 oranges
41,"A book is on sale for 35% off. If the original price is $40, what is the sale price?",Discount = 0.35 × 40 = $14 → Sale price = 40 - 14 = $26
42,"The volume of a rectangular prism is 120 cm³. If the length is 10 cm and width is 4 cm, what is the height?",Volume = length × width × height → 120 = 10 × 4 × h → h = 3 cm
43,"If a bicycle costs $300 and you pay $75 upfront, how much is left to pay?",Remaining = 300 - 75 = $225
44,The temperature increased by 8°C to reach 25°C. What was the original temperature?,Original = 25 - 8 = 17°C
45,"If 60% of students pass a test and there are 150 students, how many fail?",Pass = 0.6 × 150 = 90 → Fail = 150 - 90 = 60 students
46,A runner completes 5 km in 25 minutes. What is their speed in km/h?,Speed = (5 km / 25 min) × (60 min/hr) = 12 km/h
47,"If a movie ticket costs $12 and you buy one for yourself and two for friends, how much do you spend?",Total = 12 × 3 = $36
48,A cube has sides of 5 cm. What is its volume?,Volume = side³ = 5³ = 125 cm³
49,"If the ratio of cats to dogs is 4:7 and there are 28 dogs, how many cats are there?",4:7 = x:28 → 7x = 112 → x = 16 cats
50,A number is increased by 25% to become 100. What was the original number?,Let x be original: 1.25x = 100 → x = 80
51,"If you divide 144 by 12, what is the quotient?",144 ÷ 12 = 12
52,"A store offers buy-one-get-one-free on items priced at $20. If you take advantage of this offer twice, how much do you spend?",Cost = 2 × 20 = $40 (you get 4 items but pay for 2)
53,"The perimeter of a rectangle is 50 cm. If the length is 15 cm, what is the width?",Perimeter = 2(l + w) → 50 = 2(15 + w) → w = 10 cm
54,"If a phone costs $600 and you get a 12% discount, how much do you pay?",Discount = 0.12 × 600 = $72 → Price = 600 - 72 = $528
55,"A bucket contains 20 liters of water. If 25% leaks out, how much water remains?",Leaked = 0.25 × 20 = 5 liters → Remaining = 20 - 5 = 15 liters
56,"If you read 30 pages of a 300-page book, what percentage have you read?",Percentage = (30/300) × 100 = 10%
57,"A parking lot charges $5 for the first hour and $2 for each additional hour. If you park for 4 hours, how much do you pay?",Cost = 5 + (2 × 3) = 5 + 6 = $11
58,"If the mean of 5 numbers is 20, and 4 of them are 15, 20, 25, 30, what is the fifth number?",Sum = 20 × 5 = 100 → Fifth number = 100 - (15 + 20 + 25 + 30) = 10
59,A plant grows 2 cm per week. How tall will it be after 10 weeks if it started at 5 cm?,Height = 5 + (2 × 10) = 25 cm
60,"If the area of a circle is 78.5 cm² (π ≈ 3.14), what is its radius?",Area = πr² → 78.5 = 3.14r² → r² = 25 → r = 5 cm
61,"A company gives a 10% bonus on salaries. If an employee earns $50,000, what is the new salary?","Bonus = 0.1 × 50,000 = $5,000 → New salary = 50,000 + 5,000 = $55,000"
62,"If a triangle has sides 3, 4, and 5, is it a right triangle? (Use Pythagorean theorem)","3² + 4² = 9 + 16 = 25 = 5² → Yes, it is a right triangle"
63,"A recipe calls for 1.5 cups of sugar. If you want to make half the recipe, how much sugar is needed?",Sugar needed = 1.5 ÷ 2 = 0.75 cups
64,"If the population doubles every 10 years and is currently 1,000, what will it be in 30 years?","After 10 years: 2,000 → After 20 years: 4,000 → After 30 years: 8,000"
65,"A student needs 70% to pass. If the test has 50 questions and each is worth 2 points, what is the passing score?",Total points = 50 × 2 = 100 → Passing score = 0.7 × 100 = 70 points
66,"If a house is valued at $250,000 and increases by 5% per year, what will it be worth after 1 year?","Increase = 0.05 × 250,000 = $12,500 → New value = 250,000 + 12,500 = $262,500"
67,A factory produces 500 items per day. How many items are produced in 30 days?,"Total = 500 × 30 = 15,000 items"
68,"If you mix 3 cups of juice with 2 cups of water, what is the ratio of juice to total liquid?",Total liquid = 3 + 2 = 5 cups → Ratio = 3:5
69,"A loan of $5,000 has a 6% annual interest rate. How much interest will you pay in 1 year?","Interest = 0.06 × 5,000 = $300"
70,"If the slope of a line is 2 and it passes through (0, 3), what is the y-intercept?",y-intercept = 3 (the b in y = mx + b)
71,A bag contains 5 red balls and 3 blue balls. What is the probability of drawing a red ball?,P(red) = 5/(5+3) = 5/8
72,"If a job pays $25/hour and you work 8 hours a day, what do you earn in 5 days?","Daily earnings = 25 × 8 = $200 → 5 days = 200 × 5 = $1,000"
73,"The sum of a number and its reciprocal is 5. If the number is positive, what is it?",Let x be the number: x + 1/x = 5 → x² - 5x + 1 = 0 → x = (5 + √21)/2 ≈ 4.79
74,"If a chord is 12 cm long and the radius is 10 cm, how far is the chord from the center?",Using Pythagorean theorem: d² + 6² = 10² → d² = 64 → d = 8 cm
75,"A person saves 15% of their income. If they earn $3,000 per month, how much do they save?","Savings = 0.15 × 3,000 = $450"
76,"If the exterior angle of a regular polygon is 30°, how many sides does it have?",Sides = 360 / 30 = 12 sides
77,A train leaves at 8 AM and travels at 60 km/h. A car leaves at 10 AM and travels at 80 km/h. When will the car catch up?,Train head start = 60 × 2 = 120 km → Time for car to catch up = 120 / (80 - 60) = 6 hours → 4 PM
78,"If the product of two numbers is 24 and their sum is 10, what are the numbers?","Let x and y be numbers: xy = 24, x + y = 10 → x² - 10x + 24 = 0 → x = 6, y = 4"
79,"A painting is 60 cm by 80 cm. If you frame it with a 5 cm border, what are the outer dimensions?","Outer length = 60 + 2(5) = 70 cm, Outer width = 80 + 2(5) = 90 cm"
80,"If a quiz has 20 questions and you answer 18 correctly, what is your percentage score?",Percentage = (18/20) × 100 = 90%
81,"A ball's bounce height decreases by 20% each time. If it starts at 200 cm, what is the height of the 3rd bounce?",1st bounce: 200 × 0.8 = 160 cm → 2nd bounce: 160 × 0.8 = 128 cm → 3rd bounce: 128 × 0.8 = 102.4 cm
82,"If the least common multiple of two numbers is 60 and the greatest common divisor is 5, and one number is 15, what is the other?",LCM = (a × b) / GCD → 60 = (15 × b) / 5 → b = 20
83,A cylindrical tank has a radius of 3 m and height of 10 m. What is its volume? (Use π ≈ 3.14),Volume = πr²h = 3.14 × 3² × 10 = 282.6 m³
84,"If you buy an item for $100 and sell it for $150, what is the profit percentage?",Profit = 150 - 100 = $50 → Profit % = (50/100) × 100 = 50%
85,"A class has a boy-to-girl ratio of 2:3. If there are 10 boys, how many girls are there?",2:3 = 10:x → 2x = 30 → x = 15 girls
86,"If the median of 5 numbers is 30 and the numbers are 10, 20, x, 40, 50, what is x?","When ordered: 10, 20, x, 40, 50 → Median is the middle value = x = 30"
87,"A rope is cut into 3 pieces in the ratio 2:3:4. If the total length is 36 m, what is the longest piece?",Ratio sum = 2 + 3 + 4 = 9 → Longest piece = (4/9) × 36 = 16 m
88,"If a car uses 1 liter of fuel per 10 km and fuel costs $1.50 per liter, what is the cost per km?",Cost per km = (1/10) × 1.50 = $0.15
89,The angles of a quadrilateral are in the ratio 1:2:3:4. What is the largest angle?,Angle sum = 360° → Largest angle = (4/10) × 360 = 144°
90,"If the probability of rain is 40%, what is the probability it will not rain?",P(no rain) = 1 - 0.4 = 0.6 or 60%
91,"A store marks up items by 60% from cost. If an item costs $25 to make, what is the selling price?",Markup = 0.6 × 25 = $15 → Selling price = 25 + 15 = $40
92,"If the diagonal of a square is 10 cm, what is the area of the square?",Diagonal = side√2 → 10 = side√2 → side = 10/√2 ≈ 7.07 cm → Area = 50 cm²
93,"A farmer has 120 acres. If 30% is planted with corn, 25% with wheat, and the rest with soybeans, how many acres have soybeans?",Soybeans = (100 - 30 - 25)% of 120 = 45% × 120 = 54 acres
94,"If you invest $2,000 at 4% simple interest for 3 years, how much will you have?","Interest = 2,000 × 0.04 × 3 = $240 → Total = 2,000 + 240 = $2,240"
95,"A recipe uses butter and sugar in the ratio 1:2. If you use 150g of butter, how much sugar is needed?",1:2 = 150:x → x = 300g sugar
96,"If the temperature is -5°C and rises by 12°C, what is the new temperature?",New temperature = -5 + 12 = 7°C
97,"A ladder is 10 m long and leans against a wall. If the base is 6 m from the wall, how high is the ladder reach?",Height² + 6² = 10² → Height² = 64 → Height = 8 m
98,"If the average price of 4 items is $25, and three items cost $20, $30, and $15, what is the cost of the fourth item?",Total = 25 × 4 = $100 → Fourth item = 100 - (20 + 30 + 15) = $35
99,"A store sells 500 items per week. If demand increases by 10% each week, how many items will be sold in week 2?",Week 2 sales = 500 × 1.1 = 550 items
100,"If a triangle has angles of 60°, 60°, and 60°, what type of triangle is it?",It is an equilateral triangle (all angles equal and all sides equal)"""

# ---------------------------------------------------------
# 2. TOPIC CLASSIFICATION & DATA MANAGEMENT
# ---------------------------------------------------------
class QuestionBank:
    """
    Manages the provided 100-question dataset.
    Automatically categorizes questions into topics based on keywords.
    """
    def __init__(self):
        self.db = {} # Format: {topic_name: [list_of_question_dicts]}
        self.all_topics = []
        self._load_and_categorize_dataset()

    def _categorize_problem(self, text):
        """Simple keyword-based topic tagging"""
        text = text.lower()
        if any(w in text for w in ['area', 'perimeter', 'volume', 'triangle', 'square', 'circle', 'radius', 'rectangle', 'angle', 'slope', 'geometry', 'polygon', 'diagonal']):
            return 'geometry'
        elif any(w in text for w in ['ratio', 'proportion', 'scale', 'percentage', '%', 'discount', 'tax', 'interest', 'profit', 'rate', 'cost', 'price']):
            return 'ratios_and_percentages'
        elif any(w in text for w in ['speed', 'distance', 'time', 'km', 'hour', 'velocity']):
            return 'physics_kinematics'
        elif any(w in text for w in ['probability', 'mean', 'median', 'average', 'chance', 'roll']):
            return 'statistics_probability'
        elif any(w in text for w in ['x', 'solve', 'equation', 'sum', 'difference', 'product', 'quotient', 'number', 'algebra']):
            return 'algebra_arithmetic'
        else:
            return 'general_word_problems'

    def _extract_ground_truth(self, solution_text):
        """Smarter extraction prioritizing explicit answers."""
        import re
        
        # Priority 1: Look for "x = 50" or "result = 50"
        explicit_match = re.findall(r"=\s*(\d+\.?\d*)", solution_text)
        if explicit_match:
            return float(explicit_match[-1])
            
        # Priority 2: Look for numbers, but ignore the input numbers from the question text
        # (This is hard to do perfectly without the question text, so we stick to last number)
        matches = re.findall(r"[-+]?\d*\.\d+|\d+", solution_text)
        if matches:
            return float(matches[-1])
        return 0.0

    def _load_and_categorize_dataset(self):
        """Parses the CSV string and organizes by topic"""
        reader = csv.DictReader(io.StringIO(RAW_DATASET))
        
        for row in reader:
            topic = self._categorize_problem(row['problem_text'])
            ground_truth_val = self._extract_ground_truth(row['solution_text'])
            
            if topic not in self.db:
                self.db[topic] = []
                
            self.db[topic].append({
                "id": row['problem_id'],
                "q": row['problem_text'],
                "solution_text": row['solution_text'],
                "ground_truth_numeric": ground_truth_val
            })
        
        self.all_topics = list(self.db.keys())
        print(f"[DATA] Dataset Loaded: {sum(len(v) for v in self.db.values())} questions across {len(self.all_topics)} topics.")

    def get_question(self, topic):
        """Get a random question for a specific topic"""
        if topic not in self.db or not self.db[topic]:
            # Fallback to any topic if specific one is empty
            topic = random.choice(self.all_topics)
        return random.choice(self.db[topic])

# ---------------------------------------------------------
# 3. REINFORCEMENT LEARNING AGENT (BANDIT)
# ---------------------------------------------------------
# =============================================================================
#  REPLACE FROM "class TopicBandit" DOWNWARDS WITH THIS CODE
# =============================================================================

import random
import json
import os
import time

# =============================================================================
#  ADAPTIVE PRACTICE FORUM (REINFORCEMENT AGENT LAYER) - WITH DATASET INTEGRATION
# =============================================================================

import random
import re
import csv
import io
import sys
import io
# Force standard output to handle Unicode/Emojis on Windows
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# ---------------------------------------------------------
# 1. THE DATASET (Embedded for portability)
# ---------------------------------------------------------
RAW_DATASET = """problem_id,problem_text,solution_text
1,A car covers 150 km in 3 hours. What is its speed?,Speed = Distance / Time = 150 / 3 = 50 km/hr
2,The sum of two numbers is 40 and their difference is 10. Find the numbers.,"Let x + y = 40, x − y = 10 → x = 25, y = 15"
3,"If a book costs $12 and you buy 5 books, how much do you spend?",Total cost = 12 × 5 = $60
4,A rectangle has a length of 10 cm and width of 6 cm. What is its area?,Area = Length × Width = 10 × 6 = 60 cm²
5,"If 40% of a number is 80, what is the number?",Let x be the number: 0.4x = 80 → x = 200
6,A train travels at 60 km/h. How far does it travel in 2.5 hours?,Distance = Speed × Time = 60 × 2.5 = 150 km
7,The perimeter of a square is 36 cm. What is the length of each side?,Perimeter = 4 × side → 36 = 4s → s = 9 cm
8,"If 3 pens cost $6, how much do 8 pens cost?",Cost per pen = 6/3 = $2 → 8 pens = 8 × 2 = $16
9,The sum of three consecutive numbers is 51. Find the numbers.,"Let x, x+1, x+2 be the numbers: x + (x+1) + (x+2) = 51 → x = 16. Numbers are 16, 17, 18"
10,A store offers a 25% discount on a $80 item. What is the sale price?,Discount = 0.25 × 80 = $20 → Sale price = 80 - 20 = $60
11,"If the ratio of boys to girls is 3:2 and there are 15 boys, how many girls are there?",3:2 = 15:x → 3x = 30 → x = 10 girls
12,A circle has a radius of 5 cm. What is its circumference? (Use π ≈ 3.14),Circumference = 2πr = 2 × 3.14 × 5 = 31.4 cm
13,"If a worker earns $15 per hour and works 40 hours a week, what is the weekly earnings?",Weekly earnings = 15 × 40 = $600
14,The area of a triangle is 30 cm² and its base is 10 cm. What is the height?,Area = (Base × Height)/2 → 30 = (10 × h)/2 → h = 6 cm
15,"If you have $500 and spend 30% of it, how much is left?",Amount spent = 0.3 × 500 = $150 → Amount left = 500 - 150 = $350
16,A recipe requires 2 cups of flour for 24 cookies. How much flour is needed for 36 cookies?,Proportion: 2/24 = x/36 → x = 3 cups
17,"If the average of 4 numbers is 25, what is their sum?",Sum = Average × Count = 25 × 4 = 100
18,A tank holds 500 liters and is 60% full. How many liters are in the tank?,Volume = 0.6 × 500 = 300 liters
19,"If x + 5 = 20, what is the value of x?",x = 20 - 5 = 15
20,The cost of 6 notebooks is $18. What is the cost of 10 notebooks?,Cost per notebook = 18/6 = $3 → 10 notebooks = 10 × 3 = $30
21,"If a car depreciates by 15% each year and costs $20,000 now, what will it cost after 1 year?","Depreciation = 0.15 × 20,000 = $3,000 → New price = 20,000 - 3,000 = $17,000"
22,"The sum of angles in a triangle is 180°. If two angles are 50° and 70°, what is the third angle?",Third angle = 180 - 50 - 70 = 60°
23,"If you invest $1,000 at 5% annual interest, how much interest will you earn in 1 year?","Interest = 0.05 × 1,000 = $50"
24,"A photo is 8 inches by 6 inches. If you enlarge it by a scale factor of 1.5, what are the new dimensions?","New length = 8 × 1.5 = 12 inches, New width = 6 × 1.5 = 9 inches"
25,"If the population of a city increases by 20% and was 100,000, what is the new population?","Increase = 0.2 × 100,000 = 20,000 → New population = 100,000 + 20,000 = 120,000"
26,"A student scored 85, 90, and 88 on three tests. What is the average score?",Average = (85 + 90 + 88)/3 = 263/3 ≈ 87.67
27,"If a recipe serves 4 people and uses 2 eggs, how many eggs are needed to serve 10 people?",Proportion: 2/4 = x/10 → x = 5 eggs
28,"The distance between two cities is 300 km. If a car travels at 75 km/h, how long does it take?",Time = Distance / Speed = 300 / 75 = 4 hours
29,"If the probability of an event is 0.25, what is the probability it does not occur?",P(not occurring) = 1 - 0.25 = 0.75
30,A store buys items for $50 and sells them for $80. What is the profit margin percentage?,Profit = 80 - 50 = $30 → Profit margin = (30/50) × 100 = 60%
31,"If 15% of a number is 45, what is 30% of that number?",Number = 45/0.15 = 300 → 30% of 300 = 0.3 × 300 = 90
32,A rectangular garden is 20 meters long and 15 meters wide. What is its perimeter?,Perimeter = 2(length + width) = 2(20 + 15) = 70 meters
33,"If a subscription costs $10 per month, how much does it cost for 2 years?",Cost = 10 × 12 × 2 = $240
34,The area of a square is 64 cm². What is its perimeter?,Side = √64 = 8 cm → Perimeter = 4 × 8 = 32 cm
35,"If you save $50 per week, how much will you save in 1 year?","Annual savings = 50 × 52 = $2,600"
36,"A ball is dropped from 100 meters. If it bounces to 80% of its previous height, how high is the first bounce?",First bounce height = 0.8 × 100 = 80 meters
37,"If the tax rate is 8% and an item costs $50, what is the total cost including tax?",Tax = 0.08 × 50 = $4 → Total = 50 + 4 = $54
38,"A class has 30 students. If 20% are absent, how many are present?",Absent = 0.2 × 30 = 6 → Present = 30 - 6 = 24
39,"If 2x + 3 = 13, what is the value of x?",2x = 13 - 3 = 10 → x = 5
40,"The ratio of apples to oranges in a basket is 5:3. If there are 15 apples, how many oranges are there?",5:3 = 15:x → 5x = 45 → x = 9 oranges
41,"A book is on sale for 35% off. If the original price is $40, what is the sale price?",Discount = 0.35 × 40 = $14 → Sale price = 40 - 14 = $26
42,"The volume of a rectangular prism is 120 cm³. If the length is 10 cm and width is 4 cm, what is the height?",Volume = length × width × height → 120 = 10 × 4 × h → h = 3 cm
43,"If a bicycle costs $300 and you pay $75 upfront, how much is left to pay?",Remaining = 300 - 75 = $225
44,The temperature increased by 8°C to reach 25°C. What was the original temperature?,Original = 25 - 8 = 17°C
45,"If 60% of students pass a test and there are 150 students, how many fail?",Pass = 0.6 × 150 = 90 → Fail = 150 - 90 = 60 students
46,A runner completes 5 km in 25 minutes. What is their speed in km/h?,Speed = (5 km / 25 min) × (60 min/hr) = 12 km/h
47,"If a movie ticket costs $12 and you buy one for yourself and two for friends, how much do you spend?",Total = 12 × 3 = $36
48,A cube has sides of 5 cm. What is its volume?,Volume = side³ = 5³ = 125 cm³
49,"If the ratio of cats to dogs is 4:7 and there are 28 dogs, how many cats are there?",4:7 = x:28 → 7x = 112 → x = 16 cats
50,A number is increased by 25% to become 100. What was the original number?,Let x be original: 1.25x = 100 → x = 80
51,"If you divide 144 by 12, what is the quotient?",144 ÷ 12 = 12
52,"A store offers buy-one-get-one-free on items priced at $20. If you take advantage of this offer twice, how much do you spend?",Cost = 2 × 20 = $40 (you get 4 items but pay for 2)
53,"The perimeter of a rectangle is 50 cm. If the length is 15 cm, what is the width?",Perimeter = 2(l + w) → 50 = 2(15 + w) → w = 10 cm
54,"If a phone costs $600 and you get a 12% discount, how much do you pay?",Discount = 0.12 × 600 = $72 → Price = 600 - 72 = $528
55,"A bucket contains 20 liters of water. If 25% leaks out, how much water remains?",Leaked = 0.25 × 20 = 5 liters → Remaining = 20 - 5 = 15 liters
56,"If you read 30 pages of a 300-page book, what percentage have you read?",Percentage = (30/300) × 100 = 10%
57,"A parking lot charges $5 for the first hour and $2 for each additional hour. If you park for 4 hours, how much do you pay?",Cost = 5 + (2 × 3) = 5 + 6 = $11
58,"If the mean of 5 numbers is 20, and 4 of them are 15, 20, 25, 30, what is the fifth number?",Sum = 20 × 5 = 100 → Fifth number = 100 - (15 + 20 + 25 + 30) = 10
59,A plant grows 2 cm per week. How tall will it be after 10 weeks if it started at 5 cm?,Height = 5 + (2 × 10) = 25 cm
60,"If the area of a circle is 78.5 cm² (π ≈ 3.14), what is its radius?",Area = πr² → 78.5 = 3.14r² → r² = 25 → r = 5 cm
61,"A company gives a 10% bonus on salaries. If an employee earns $50,000, what is the new salary?","Bonus = 0.1 × 50,000 = $5,000 → New salary = 50,000 + 5,000 = $55,000"
62,"If a triangle has sides 3, 4, and 5, is it a right triangle? (Use Pythagorean theorem)","3² + 4² = 9 + 16 = 25 = 5² → Yes, it is a right triangle"
63,"A recipe calls for 1.5 cups of sugar. If you want to make half the recipe, how much sugar is needed?",Sugar needed = 1.5 ÷ 2 = 0.75 cups
64,"If the population doubles every 10 years and is currently 1,000, what will it be in 30 years?","After 10 years: 2,000 → After 20 years: 4,000 → After 30 years: 8,000"
65,"A student needs 70% to pass. If the test has 50 questions and each is worth 2 points, what is the passing score?",Total points = 50 × 2 = 100 → Passing score = 0.7 × 100 = 70 points
66,"If a house is valued at $250,000 and increases by 5% per year, what will it be worth after 1 year?","Increase = 0.05 × 250,000 = $12,500 → New value = 250,000 + 12,500 = $262,500"
67,A factory produces 500 items per day. How many items are produced in 30 days?,"Total = 500 × 30 = 15,000 items"
68,"If you mix 3 cups of juice with 2 cups of water, what is the ratio of juice to total liquid?",Total liquid = 3 + 2 = 5 cups → Ratio = 3:5
69,"A loan of $5,000 has a 6% annual interest rate. How much interest will you pay in 1 year?","Interest = 0.06 × 5,000 = $300"
70,"If the slope of a line is 2 and it passes through (0, 3), what is the y-intercept?",y-intercept = 3 (the b in y = mx + b)
71,A bag contains 5 red balls and 3 blue balls. What is the probability of drawing a red ball?,P(red) = 5/(5+3) = 5/8
72,"If a job pays $25/hour and you work 8 hours a day, what do you earn in 5 days?","Daily earnings = 25 × 8 = $200 → 5 days = 200 × 5 = $1,000"
73,"The sum of a number and its reciprocal is 5. If the number is positive, what is it?",Let x be the number: x + 1/x = 5 → x² - 5x + 1 = 0 → x = (5 + √21)/2 ≈ 4.79
74,"If a chord is 12 cm long and the radius is 10 cm, how far is the chord from the center?",Using Pythagorean theorem: d² + 6² = 10² → d² = 64 → d = 8 cm
75,"A person saves 15% of their income. If they earn $3,000 per month, how much do they save?","Savings = 0.15 × 3,000 = $450"
76,"If the exterior angle of a regular polygon is 30°, how many sides does it have?",Sides = 360 / 30 = 12 sides
77,A train leaves at 8 AM and travels at 60 km/h. A car leaves at 10 AM and travels at 80 km/h. When will the car catch up?,Train head start = 60 × 2 = 120 km → Time for car to catch up = 120 / (80 - 60) = 6 hours → 4 PM
78,"If the product of two numbers is 24 and their sum is 10, what are the numbers?","Let x and y be numbers: xy = 24, x + y = 10 → x² - 10x + 24 = 0 → x = 6, y = 4"
79,"A painting is 60 cm by 80 cm. If you frame it with a 5 cm border, what are the outer dimensions?","Outer length = 60 + 2(5) = 70 cm, Outer width = 80 + 2(5) = 90 cm"
80,"If a quiz has 20 questions and you answer 18 correctly, what is your percentage score?",Percentage = (18/20) × 100 = 90%
81,"A ball's bounce height decreases by 20% each time. If it starts at 200 cm, what is the height of the 3rd bounce?",1st bounce: 200 × 0.8 = 160 cm → 2nd bounce: 160 × 0.8 = 128 cm → 3rd bounce: 128 × 0.8 = 102.4 cm
82,"If the least common multiple of two numbers is 60 and the greatest common divisor is 5, and one number is 15, what is the other?",LCM = (a × b) / GCD → 60 = (15 × b) / 5 → b = 20
83,A cylindrical tank has a radius of 3 m and height of 10 m. What is its volume? (Use π ≈ 3.14),Volume = πr²h = 3.14 × 3² × 10 = 282.6 m³
84,"If you buy an item for $100 and sell it for $150, what is the profit percentage?",Profit = 150 - 100 = $50 → Profit % = (50/100) × 100 = 50%
85,"A class has a boy-to-girl ratio of 2:3. If there are 10 boys, how many girls are there?",2:3 = 10:x → 2x = 30 → x = 15 girls
86,"If the median of 5 numbers is 30 and the numbers are 10, 20, x, 40, 50, what is x?","When ordered: 10, 20, x, 40, 50 → Median is the middle value = x = 30"
87,"A rope is cut into 3 pieces in the ratio 2:3:4. If the total length is 36 m, what is the longest piece?",Ratio sum = 2 + 3 + 4 = 9 → Longest piece = (4/9) × 36 = 16 m
88,"If a car uses 1 liter of fuel per 10 km and fuel costs $1.50 per liter, what is the cost per km?",Cost per km = (1/10) × 1.50 = $0.15
89,The angles of a quadrilateral are in the ratio 1:2:3:4. What is the largest angle?,Angle sum = 360° → Largest angle = (4/10) × 360 = 144°
90,"If the probability of rain is 40%, what is the probability it will not rain?",P(no rain) = 1 - 0.4 = 0.6 or 60%
91,"A store marks up items by 60% from cost. If an item costs $25 to make, what is the selling price?",Markup = 0.6 × 25 = $15 → Selling price = 25 + 15 = $40
92,"If the diagonal of a square is 10 cm, what is the area of the square?",Diagonal = side√2 → 10 = side√2 → side = 10/√2 ≈ 7.07 cm → Area = 50 cm²
93,"A farmer has 120 acres. If 30% is planted with corn, 25% with wheat, and the rest with soybeans, how many acres have soybeans?",Soybeans = (100 - 30 - 25)% of 120 = 45% × 120 = 54 acres
94,"If you invest $2,000 at 4% simple interest for 3 years, how much will you have?","Interest = 2,000 × 0.04 × 3 = $240 → Total = 2,000 + 240 = $2,240"
95,"A recipe uses butter and sugar in the ratio 1:2. If you use 150g of butter, how much sugar is needed?",1:2 = 150:x → x = 300g sugar
96,"If the temperature is -5°C and rises by 12°C, what is the new temperature?",New temperature = -5 + 12 = 7°C
97,"A ladder is 10 m long and leans against a wall. If the base is 6 m from the wall, how high is the ladder reach?",Height² + 6² = 10² → Height² = 64 → Height = 8 m
98,"If the average price of 4 items is $25, and three items cost $20, $30, and $15, what is the cost of the fourth item?",Total = 25 × 4 = $100 → Fourth item = 100 - (20 + 30 + 15) = $35
99,"A store sells 500 items per week. If demand increases by 10% each week, how many items will be sold in week 2?",Week 2 sales = 500 × 1.1 = 550 items
100,"If a triangle has angles of 60°, 60°, and 60°, what type of triangle is it?",It is an equilateral triangle (all angles equal and all sides equal)"""

# ---------------------------------------------------------
# 2. TOPIC CLASSIFICATION & DATA MANAGEMENT
# ---------------------------------------------------------
class QuestionBank:
    """
    Manages the provided 100-question dataset.
    Automatically categorizes questions into topics based on keywords.
    """
    def __init__(self):
        self.db = {} # Format: {topic_name: [list_of_question_dicts]}
        self.all_topics = []
        self._load_and_categorize_dataset()

    def _categorize_problem(self, text):
        """Simple keyword-based topic tagging"""
        text = text.lower()
        if any(w in text for w in ['area', 'perimeter', 'volume', 'triangle', 'square', 'circle', 'radius', 'rectangle', 'angle', 'slope', 'geometry', 'polygon', 'diagonal']):
            return 'geometry'
        elif any(w in text for w in ['ratio', 'proportion', 'scale', 'percentage', '%', 'discount', 'tax', 'interest', 'profit', 'rate', 'cost', 'price']):
            return 'ratios_and_percentages'
        elif any(w in text for w in ['speed', 'distance', 'time', 'km', 'hour', 'velocity']):
            return 'physics_kinematics'
        elif any(w in text for w in ['probability', 'mean', 'median', 'average', 'chance', 'roll']):
            return 'statistics_probability'
        elif any(w in text for w in ['x', 'solve', 'equation', 'sum', 'difference', 'product', 'quotient', 'number', 'algebra']):
            return 'algebra_arithmetic'
        else:
            return 'general_word_problems'

    def _extract_ground_truth(self, solution_text):
        """
        Extracts the final numerical answer from the solution text.
        Example: "Speed = 150/3 = 50 km/hr" -> 50.0
        """
        # Look for the last number in the string
        matches = re.findall(r"[-+]?\d*\.\d+|\d+", solution_text)
        if matches:
            return float(matches[-1])
        return 0.0

    def _load_and_categorize_dataset(self):
        """Parses the CSV string and organizes by topic"""
        reader = csv.DictReader(io.StringIO(RAW_DATASET))
        
        for row in reader:
            topic = self._categorize_problem(row['problem_text'])
            ground_truth_val = self._extract_ground_truth(row['solution_text'])
            
            if topic not in self.db:
                self.db[topic] = []
                
            self.db[topic].append({
                "id": row['problem_id'],
                "q": row['problem_text'],
                "solution_text": row['solution_text'],
                "ground_truth_numeric": ground_truth_val
            })
        
        self.all_topics = list(self.db.keys())
        print(f"[DATA] Dataset Loaded: {sum(len(v) for v in self.db.values())} questions across {len(self.all_topics)} topics.")

    def get_question(self, topic):
        """Get a random question for a specific topic"""
        if topic not in self.db or not self.db[topic]:
            # Fallback to any topic if specific one is empty
            topic = random.choice(self.all_topics)
        return random.choice(self.db[topic])

# ---------------------------------------------------------
# 3. REINFORCEMENT LEARNING AGENT (BANDIT)
# ---------------------------------------------------------
# =============================================================================
#  REPLACE FROM "class TopicBandit" DOWNWARDS WITH THIS CODE
# =============================================================================

import random
import json
import os
import time

# =============================================================================
#  REPLACE FROM "class TopicBandit" DOWNWARDS WITH THIS CODE
# =============================================================================

import random
import json
import os
import time
import math
import re
from collections import Counter

# ---------------------------------------------------------
# 3. SOPHISTICATED REINFORCEMENT AGENT (THOMPSON SAMPLING)
# ---------------------------------------------------------
class ThompsonBandit:
    """
    A Bayesian Reinforcement Learning Agent using Interleaved Thompson Sampling.
    
    1. MODEL: Models student mastery as a Beta Distribution B(alpha, beta).
       - Alpha: Evidence of Success (Correct + 1)
       - Beta: Evidence of Failure (Incorrect + 1)
       
    2. POLICY: Uses 'Interleaved Practice' instead of pure Greedy selection.
       - 60% Focus (Weak Spots) -> To maximize learning.
       - 40% Review (Strengths) -> To prevent forgetting & build confidence.
    """
    def __init__(self, topics):
        # Initialize Uniform Priors: Alpha=1, Beta=1 ("I know nothing")
        self.params = {topic: {'alpha': 1.0, 'beta': 1.0} for topic in topics}

    def select_topics(self, k=5):
        """
        Sophisticated Selection Logic:
        Samples from posterior distributions to determine the 'Optimal Mix'.
        """
        # 1. Thompson Sampling Step
        # Draw a random sample from every topic's curve.
        topic_samples = []
        for topic, p in self.params.items():
            sampled_mastery = random.betavariate(p['alpha'], p['beta'])
            topic_samples.append((topic, sampled_mastery))
        
        # 2. Sort by Sampled Mastery (Lowest = Weakest)
        topic_samples.sort(key=lambda x: x[1])
        
        # 3. Define the Split (The "Anti-Punishment" Logic)
        n_focus = int(k * 0.6)  # 60% Focus (Weakest)
        n_review = k - n_focus  # 40% Review (Strongest)
        
        # 4. Pick Focus Topics (The bottom N weakest)
        focus_selection = [t[0] for t in topic_samples[:n_focus]]
        
        # 5. Pick Review Topics (Randomly sample from the top 50% strongest)
        # We don't just pick the #1 best, we mix it up to keep it fresh.
        n_strong_pool = max(1, len(topic_samples) // 2)
        strong_pool = [t[0] for t in topic_samples[-n_strong_pool:]]
        
        # Safety: If pool is too small, just repeat
        if len(strong_pool) < n_review:
            review_selection = random.choices(strong_pool, k=n_review)
        else:
            review_selection = random.sample(strong_pool, n_review)
            
        final_mix = focus_selection + review_selection
        random.shuffle(final_mix) # Shuffle so the user doesn't know which is which
        
        return final_mix

    def update(self, topic, is_correct):
        """Bayesian Posterior Update"""
        if is_correct:
            # Reward: Shift curve Right (Confidence in Mastery increases)
            self.params[topic]['alpha'] += 1.0
        else:
            # Penalty: Shift curve Left (Confidence in Weakness increases)
            self.params[topic]['beta'] += 1.0

    def get_stats(self, topic):
        """Returns Mean Mastery % and Bayesian Certainty %"""
        a = self.params[topic]['alpha']
        b = self.params[topic]['beta']
        
        # Mean of Beta Distribution
        mean = a / (a + b)
        
        # Calculate a "Certainty Score" (0-100%) based on sample size
        # As samples (a+b) increase, certainty approaches 100
        total_evidence = a + b
        certainty = min(100, (1 - (1/(total_evidence/2 + 1))) * 100)
        
        return mean, certainty

    def predict_next_batch(self, k=5):
        """Simulates the next selection to show the user a preview"""
        topics = self.select_topics(k)
        return Counter(topics)

    def save_profile(self, filename="bayes_model.json"):
        try:
            with open(filename, 'w') as f:
                json.dump(self.params, f)
            print(f"💾 [BAYES] Probabilistic model saved to '{filename}'")
        except Exception as e:
            print(f"❌ Error saving: {e}")

    def load_profile(self, filename="bayes_model.json"):
        if not os.path.exists(filename):
            print("⚠️ No prior distribution found. Starting with Uniform Priors.")
            return False
        try:
            with open(filename, 'r') as f:
                self.params.update(json.load(f))
            print(f"📂 [BAYES] Loaded posterior distributions.")
            return True
        except Exception as e:
            print(f"❌ Error loading: {e}")
            return False

# ---------------------------------------------------------
# 4. PRACTICE FORUM (VISUALIZATION & CONTROL)
# ---------------------------------------------------------
class PracticeForum:
    def __init__(self):
        self.bank = QuestionBank()
        # USE THE SOPHISTICATED AGENT
        self.bandit = ThompsonBandit(self.bank.all_topics)
        
        # Connect to solver (Robust check)
        try:
            self.solver = SymbolicSolver()
        except:
            print("⚠️ Warning: SymbolicSolver class not found. Grading may fail.")

    def grade_submission(self, user_input, ground_truth_numeric):
        """Robust grading with relaxed tolerance and time handling."""
        import re
        
        # Added .replace(",", "") to fix the 15,000 issue
        clean_input = user_input.upper().replace("$", "").replace("KM", "").replace("%", "").replace(",", "").strip()

        # 1. SPECIAL CHECK: Is this a word answer? (e.g. "Equilateral")
        # If user typed words but no equals sign, and ground truth is a number, 
        # it's definitely wrong (or the system can't grade it).
        if re.search(r'[A-Z]{2,}', clean_input) and "=" not in clean_input and "PM" not in clean_input and "AM" not in clean_input:
             return False

        # 2. SPECIAL CHECK: Time (e.g. "4 PM")
        if "PM" in clean_input or "AM" in clean_input:
            nums = re.findall(r"\d+", clean_input)
            if nums:
                user_val = float(nums[0])
                if abs(user_val - float(ground_truth_numeric)) < 0.1:
                    return True

        # 3. DIRECT NUMBER MATCH (Relaxed Tolerance)
        try:
            numbers = re.findall(r"[-+]?\d*\.\d+|\d+", clean_input)
            if numbers:
                for num in numbers:
                    # Tolerance increased to 0.5 to allow rounding (e.g. 87 vs 87.67)
                    if abs(float(num) - float(ground_truth_numeric)) < 0.5:
                        return True
        except: pass

        # 4. SYMBOLIC MATCH
        try:
            solve_result = self.solver([clean_input])
            if solve_result.success and solve_result.solution:
                for val in solve_result.solution.values():
                    if abs(float(val) - float(ground_truth_numeric)) < 0.5:
                        return True
        except: pass
        
        return False

    def visualize_dashboard(self):
        """Visualizes the Probability Distributions clearly"""
        print("\n🧠 BAYESIAN KNOWLEDGE STATE (The AI's Model of You):")
        print(f"   {'Topic'.ljust(25)} | {'Mastery'.ljust(10)} | {'Confidence'.ljust(10)} | Status")
        print("-" * 75)
        
        # Sort by Mean Mastery (Weakest First)
        topics = sorted(self.bandit.params.keys(), 
                       key=lambda t: self.bandit.get_stats(t)[0])
        
        for t in topics:
            mean, certainty = self.bandit.get_stats(t)
            mastery_pct = mean * 100
            
            # Visual Bar Logic
            bar_len = int(mastery_pct / 5)
            bar = "█" * bar_len
            empty = "░" * (20 - bar_len)
            
            # Status Logic
            if mastery_pct < 40: status = "🔴 FOCUS"
            elif mastery_pct > 80: status = "🟢 STRONG"
            else: status = "🟡 LEARNING"
            
            # Low confidence warning
            conf_str = f"{int(certainty)}%"
            if certainty < 20: conf_str += " (?)"
            
            print(f"   {t.ljust(25)} | {bar}{empty} {int(mastery_pct)}%  | {conf_str.ljust(10)} | {status}")

    def run_interactive_loop(self):
        print("\n" + "="*60)
        print("🎓 CALCMATE: INTELLIGENT ADAPTIVE TUTOR")
        print("   Engine: Bayesian Thompson Sampling (Interleaved)")
        print("="*60)

        choice = input("Load previous Bayesian Model? (y/n): ").lower().strip()
        if choice == 'y': self.bandit.load_profile()
        else: print("✨ Initializing Uniform Priors (α=1, β=1)...")

        batch_count = 1
        n_questions = 3 # Default

        while True:
            # --- 1. THE PREVIEW (Deterministic) ---
            # We generate the topics ONCE here and store them
            current_batch_topics = self.bandit.select_topics(k=n_questions)
            
            print(f"\n🔮 PREDICTING BATCH #{batch_count} COMPOSITION:")
            preview = Counter(current_batch_topics) # Count them for display
            
            print("   The AI plans to assign:")
            for topic, count in preview.items():
                mastery, _ = self.bandit.get_stats(topic)
                # Logic: If mastery < 50%, it's likely a focus topic
                reason = "(Weak Spot)" if mastery < 0.5 else "(Review)"
                print(f"   👉 {count}x {topic.replace('_', ' ').title()} {reason}")
            
            confirm = input("\n   Ready to start? (y/n/change_count): ").strip().lower()
            if confirm.isdigit():
                n_questions = int(confirm)
                print(f"   Updated batch size to {n_questions}.")
                continue # Re-generate preview with new size
            elif confirm != 'y':
                print("   👋 Session paused.")
                break

            # --- 2. THE SESSION ---
            print(f"\n📅 STARTING BATCH #{batch_count}")
            print("-" * 30)
            
            score = 0
            
            # Use the PRE-GENERATED list (current_batch_topics)
            for i, topic in enumerate(current_batch_topics, 1):
                q_data = self.bank.get_question(topic)
                if not q_data: continue

                print(f"\n📝 Q{i} [{topic.upper()}]:")
                print(f"   {q_data['q']}")
                
                user_input = input("   ✍️ Answer: ").strip()
                
                # Grading
                is_correct = self.grade_submission(user_input, q_data['ground_truth_numeric'])
                self.bandit.update(topic, is_correct)
                
                if is_correct:
                    print("   ✅ CORRECT!")
                    score += 1
                else:
                    print(f"   ❌ INCORRECT.")
                    print(f"   💡 Solution: {q_data['solution_text']}")

            # --- 3. THE REPORT ---
            print("\n" + "-"*60)
            print(f"📊 BATCH COMPLETE: {score}/{n_questions}")
            self.visualize_dashboard()
            print("-" * 60)
            
            if input("\nContinue to next batch? (y/n): ").lower().strip() != 'y':
                if input("Save learning state? (y/n): ").lower().strip() == 'y':
                    self.bandit.save_profile()

                break
            
            batch_count += 1

# =============================================================================
#  MAIN ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    print("🚀 Select Mode:")
    print("1. Standard Pipeline Test (Original)")
    print("2. Intelligent Adaptive Tutor (Bayesian)")
    
    choice = input("Enter 1 or 2: ").strip()
    
    if choice == "1":
        print("\n--- Running Standard Pipeline ---")
        # pipeline = SmartRetrievalPipeline("path/to/index", "path/to/idmap")
        print("Standard test complete (Mock).")
        
    elif choice == "2":
        forum = PracticeForum()
        forum.run_interactive_loop()
        
    else:
        print("Invalid choice. Exiting.")