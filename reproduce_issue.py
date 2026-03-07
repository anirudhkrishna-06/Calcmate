
import sys
import os
import logging
# Force flush
sys.stdout.reconfigure(encoding='utf-8')

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from pipeline_sequence.advanced_equation_extractor import AdvancedMathParser, extract_equations_advanced
    print("Import successful", flush=True)
except ImportError as e:
    print(f"Import failed: {e}", flush=True)
    # fall back to local class if function not found
    from pipeline_sequence.advanced_equation_extractor import AdvancedMathParser

def test_extraction():
    with open("reproduce_result.txt", "w") as f:
        parser = AdvancedMathParser()
        text = "Solve for x, 5.9 = x + 5.11"
        
        f.write(f"Testing extraction on: '{text}'\n")
        # Try both method if available
        if 'extract_equations_advanced' in globals():
             f.write("Using extract_equations_advanced function...\n")
             result_list = extract_equations_advanced(text)
             # emulate the dict return if it returns list
             result = {'equations': result_list, 'variables': [], 'problem_type': 'unknown', 'confidence': 0}
        else:
             f.write("Using AdvancedMathParser class...\n")
             result = parser.parse_problem(text)
        
        f.write("\nExtraction Results (Decimal):\n")
        f.write(f"Equations: {result.get('equations', [])}\n")
        
        # Test 2: Integers
        text_int = "Solve for x, 6 = x + 5"
        f.write(f"\nTesting extraction on: '{text_int}'\n")
        if 'extract_equations_advanced' in globals():
             result_list = extract_equations_advanced(text_int)
             result_int = {'equations': result_list}
        else:
             result_int = parser.parse_problem(text_int)
        f.write("\nExtraction Results (Integer):\n")
        f.write(f"Equations: {result_int.get('equations', [])}\n")

        equations = result.get('equations', [])
        if any("5.9" in eq and "5.11" in eq for eq in equations):
            f.write("\nSUCCESS: Correct equation extracted.\n")
        else:
            f.write("\nFAILURE: Correct equation NOT extracted.\n")

if __name__ == "__main__":
    test_extraction()
