
import sys
import os
import dspy
from sympy import Eq, sympify, solve, symbols

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dspy_modules import SymbolicSolver

def test_symbolic_solver():
    print("Testing SymbolicSolver with decimal equation...", flush=True)
    solver = SymbolicSolver()
    
    # Test case: 5.9 = x + 5.11
    # This was failing because ' x ' was replaced by ' * '
    equation = "5.9 = x + 5.11"
    
    print(f"Original Equation: '{equation}'", flush=True)
    cleaned = solver._clean_equation_string(equation)
    print(f"Cleaned Equation: '{cleaned}'", flush=True)
    
    if "*" in cleaned and "x" not in cleaned:
        print("FAILURE: 'x' was incorrectly replaced by '*'!", flush=True)
    elif "x" in cleaned:
        print("SUCCESS: 'x' variable preserved.", flush=True)
        
    # Try solving
    print("\nAttempting to solve...", flush=True)
    prediction = solver([equation])
    
    print(f"Prediction Success: {prediction.success}", flush=True)
    print(f"Solution: {prediction.solution}", flush=True)
    
    if prediction.success and abs(prediction.solution.get('x', 0) - 0.79) < 0.01:
         print("SUCCESS: Equation solved correctly!", flush=True)
    else:
         print("FAILURE: Equation NOT solved correctly.", flush=True)

if __name__ == "__main__":
    test_symbolic_solver()
