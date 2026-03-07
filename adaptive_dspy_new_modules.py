import dspy
import numpy as np
import os
import faiss
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sentence_transformers import SentenceTransformer
from transformers import pipeline
from langchain_community.llms import CTransformers
import requests
from pipeline_sequence.advanced_equation_extractor import extract_equations_advanced
from pipeline_sequence.canonicalizer import canonicalize_system
from pipeline_sequence.features import build_structure_vector_from_parsed
from pipeline_sequence.embedder import encode_texts, build_text_for_embedding
from pipeline_sequence.indexer_faiss import FaissIndexer
import json
import re
from typing import List, Dict, Any, Optional

from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import CountVectorizer
from sympy import symbols, solve, Eq


# --------------------------
# CTransformers LLM Initialization
# --------------------------
def initialize_ctransformers_model():
    """Initialize CTransformers model for local LLM inference"""
    try:
        print("🔄 Loading CTransformers model...")
        print("📥 This may take a few minutes on first run as the model downloads...")
        
        llm = CTransformers(
            model="TheBloke/Llama-2-7B-Chat-GGML",
            model_file="llama-2-7b-chat.ggmlv3.q4_0.bin",  # Specify model file
            model_type="llama",
            config={
                "max_new_tokens": 256, 
                "temperature": 0.5,
                "context_length": 2048  # Added context length
            }
        )
        print("✅ LLM Model Loaded Successfully!")
        return llm
    except Exception as e:
        print(f"❌ Failed to load CTransformers model: {e}")
        print("💡 The model will be downloaded automatically from Hugging Face")
        print("💡 Make sure you have sufficient disk space (~4GB) and internet connection")
        return None


# --------------------------
# Symbolic Solver
# --------------------------
class SymbolicSolver(dspy.Module):
    """Attempts to solve equations symbolically using SymPy"""
    
    def _clean_equation_string(self, eq_str):
        """Clean equation string to make it SymPy-compatible"""
        import re
        
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
    
    def forward(self, canonical_equations):
        try:
            if not canonical_equations:
                return dspy.Prediction(
                    solution={}, 
                    success=False, 
                    residuals={}, 
                    error_msg="No equations provided"
                )
            
            # Handle different types of canonical equations
            equations_to_solve = []
            for eq in canonical_equations:
                if isinstance(eq, str):
                    # Try to parse string equations - handle both expressions and equations
                    try:
                        from sympy import sympify, Eq, symbols
                        
                        # Clean up the equation string
                        cleaned_eq = self._clean_equation_string(eq)
                        
                        # First try to parse as equation (with =)
                        if '=' in cleaned_eq:
                            # Split by = and create equation
                            parts = cleaned_eq.split('=', 1)
                            if len(parts) == 2:
                                lhs = sympify(parts[0].strip())
                                rhs = sympify(parts[1].strip())
                                equations_to_solve.append(Eq(lhs, rhs))
                            else:
                                # Fallback to direct parsing
                                parsed_eq = sympify(cleaned_eq)
                                equations_to_solve.append(parsed_eq)
                        else:
                            # Parse as expression
                            parsed_eq = sympify(cleaned_eq)
                            equations_to_solve.append(parsed_eq)
                    except Exception as parse_error:
                        print(f"Failed to parse equation '{eq}': {parse_error}")
                        continue
                elif hasattr(eq, 'free_symbols'):
                    # Already a sympy expression
                    equations_to_solve.append(eq)
            
            if not equations_to_solve:
                return dspy.Prediction(
                    solution={}, 
                    success=False, 
                    residuals={}, 
                    error_msg="No valid equations to solve"
                )
            
            # Extract all symbols from equations
            syms = set()
            for e in equations_to_solve:
                if hasattr(e, 'free_symbols'):
                    syms.update(e.free_symbols)
            
            syms = sorted(syms, key=lambda x: str(x))
            
            if not syms:
                return dspy.Prediction(
                    solution={}, 
                    success=False, 
                    residuals={}, 
                    error_msg="No variables found"
                )
            
            print(f"🔍 Solving equations: {[str(eq) for eq in equations_to_solve]}")
            print(f"🔍 Variables: {[str(s) for s in syms]}")
            
            # Try to solve the system
            sol = solve(equations_to_solve, syms, dict=True)
            
            if not sol:
                return dspy.Prediction(
                    solution={}, 
                    success=False, 
                    residuals={}, 
                    error_msg="No solution found"
                )
            
            sol0 = sol[0]
            print(f"✅ Solution found: {sol0}")
            
            residuals = {}
            for e in equations_to_solve:
                try:
                    # For equations like Eq(x + y, 50), we need to evaluate the difference
                    if hasattr(e, 'lhs') and hasattr(e, 'rhs'):
                        # This is an equation: evaluate lhs - rhs
                        lhs_sub = e.lhs.subs(sol0)
                        rhs_sub = e.rhs.subs(sol0)
                        if hasattr(lhs_sub, 'evalf'):
                            lhs_val = float(lhs_sub.evalf())
                        else:
                            lhs_val = float(lhs_sub)
                        if hasattr(rhs_sub, 'evalf'):
                            rhs_val = float(rhs_sub.evalf())
                        else:
                            rhs_val = float(rhs_sub)
                        val = lhs_val - rhs_val
                    else:
                        # This is an expression: evaluate directly
                        substituted = e.subs(sol0)
                        if hasattr(substituted, 'evalf'):
                            val = float(substituted.evalf())
                        else:
                            val = float(substituted)
                    residuals[str(e)] = val
                except Exception as ex:
                    residuals[str(e)] = f"Error: {str(ex)}"
            
            # Check success - only consider numeric residuals
            numeric_residuals = [v for v in residuals.values() if isinstance(v, (int, float))]
            success = len(numeric_residuals) > 0 and all(abs(v) < 1e-6 for v in numeric_residuals)
            
            print(f"🔍 Residuals: {residuals}")
            print(f"🔍 Success: {success}")
            
            return dspy.Prediction(
                solution={str(k): float(v) for k, v in sol0.items()},
                success=success,
                residuals=residuals,
                error_msg=None
            )
        except Exception as e:
            print(f"❌ Solver error: {str(e)}")
            return dspy.Prediction(
                solution={}, 
                success=False, 
                residuals={}, 
                error_msg=f"Solver error: {str(e)}"
            )


# --------------------------
# Verifier Module
# --------------------------
class Verifier(dspy.Module):
    """Verifies if a solution satisfies the canonical equations"""
    
    def __init__(self, tolerance: float = 1e-6):
        super().__init__()
        self.tolerance = tolerance
    
    def _clean_equation_string(self, eq_str):
        """Clean equation string to make it SymPy-compatible"""
        import re
        
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
    
    def forward(self, canonical_equations, candidate_solution, retrieved_solutions=None):
        if not canonical_equations:
            return dspy.Prediction(
                verification={'ok': False, 'residuals': {}, 'error': 'No equations to verify'}
            )
        
        residuals = {}
        for e in canonical_equations:
            try:
                # Handle string equations by cleaning them first
                if isinstance(e, str):
                    cleaned_eq = self._clean_equation_string(e)
                    from sympy import sympify, Eq
                    if '=' in cleaned_eq:
                        parts = cleaned_eq.split('=', 1)
                        if len(parts) == 2:
                            lhs = sympify(parts[0].strip())
                            rhs = sympify(parts[1].strip())
                            e = Eq(lhs, rhs)
                        else:
                            e = sympify(cleaned_eq)
                    else:
                        e = sympify(cleaned_eq)
                
                substitutions = {
                    k: candidate_solution.get(str(k), 0) 
                    for k in e.free_symbols
                }
                
                # For equations like Eq(x + y, 50), we need to evaluate the difference
                if hasattr(e, 'lhs') and hasattr(e, 'rhs'):
                    # This is an equation: evaluate lhs - rhs
                    lhs_sub = e.lhs.subs(substitutions)
                    rhs_sub = e.rhs.subs(substitutions)
                    if hasattr(lhs_sub, 'evalf'):
                        lhs_val = float(lhs_sub.evalf())
                    else:
                        lhs_val = float(lhs_sub)
                    if hasattr(rhs_sub, 'evalf'):
                        rhs_val = float(rhs_sub.evalf())
                    else:
                        rhs_val = float(rhs_sub)
                    val = lhs_val - rhs_val
                else:
                    # This is an expression: evaluate directly
                    substituted = e.subs(substitutions)
                    if hasattr(substituted, 'evalf'):
                        val = float(substituted.evalf())
                    else:
                        val = float(substituted)
                
                residuals[str(e)] = {'value': val, 'satisfied': abs(val) < self.tolerance}
            except Exception as ex:
                residuals[str(e)] = {'value': None, 'error': str(ex)}
        
        ok = all(
            r.get('satisfied', False) 
            for r in residuals.values() 
            if isinstance(r, dict)
        )
        
        return dspy.Prediction(
            verification={
                'ok': ok, 
                'residuals': residuals,
                'tolerance': self.tolerance
            }
        )


# --------------------------
# LLM Reasoner with Fixed Prompting
# --------------------------
class LLMReasoner(dspy.Module):
    """Uses LLM to extract equations from problems and similar examples"""
    
    def __init__(self, llm_model=None):
        super().__init__()
        self.llm_model = llm_model if llm_model else initialize_ctransformers_model()
    
    def build_prompt(self, query: str, canonical_eqs: List, retrieved_examples: List[Dict], max_shots: int = 3) -> str:
        prompt_parts = [
        "# Math Problem Analysis\n",
        "Extract mathematical equations from the word problem following these examples.\n"
    ]
    
    # Add similar examples first with clear structure
        for i, ex in enumerate(retrieved_examples[:max_shots], 1):
            prompt_parts.append(f"\nExample {i}:")
            prompt_parts.append(f"Problem: {ex.get('text', '')}")
            if 'equations' in ex:
                eqs = ex['equations'] if isinstance(ex['equations'], list) else [ex['equations']]
                prompt_parts.append("Equations:")
                for eq in eqs:
                    prompt_parts.append(f"- {eq}")
        
        # Add current problem with clear instruction
        prompt_parts.extend([
            f"\nNow solve this problem:",
            f"Problem: {query}",
            "\nExtract the equations in the same format as the examples above.",
            "Return your answer as JSON:",
            '{"equations": ["equation1", "equation2", ...]}',
            "\nResponse:"
        ])
        
        return "\n".join(prompt_parts)

    def forward(self, query_text: str, canonical_equations: List, retrieved_examples: List[Dict]):
        try:
            # Build and send prompt
            prompt = self.build_prompt(query_text, canonical_equations, retrieved_examples)
            
            if self.llm_model:
                # Get LLM response with adjusted parameters
                response = self.llm_model.invoke(
                    prompt,
                    max_new_tokens=256,  # Shorter response focused on equations
                    temperature=0.1,     # More deterministic
                    top_p=0.9,
                    repetition_penalty=1.1
                )
                response_text = str(response)
                print(f"🔍 LLM Raw Response:\n{response_text[:200]}...")  # Debug output
                
                # Parse equations
                equations, success = self._parse_response(response_text)
                
                if not equations and canonical_equations:
                    # Fallback to canonical equations if LLM extraction failed
                    equations = [str(eq) for eq in canonical_equations]
                    success = True
                
                return dspy.Prediction(
                    llm_equations=equations,
                    llm_solution={},
                    llm_steps=response_text,
                    success=bool(equations)  # Success if we got any equations
                )
            else:
                print("⚠️ No LLM model available, using fallback extraction")
                equations = [str(eq) for eq in (canonical_equations or [])]
                return dspy.Prediction(
                    llm_equations=equations,
                    llm_solution={},
                    llm_steps="Used fallback equation extraction",
                    success=bool(equations)
                )
                
        except Exception as e:
            print(f"⚠️ LLM Reasoning failed: {str(e)}")
            return dspy.Prediction(
                llm_equations=[],
                llm_solution={},
                llm_steps=f"Error: {str(e)}",
                success=False
            )

    def _parse_response(self, response_text: str) -> tuple:
        """Enhanced response parsing to extract equations"""
        try:
            # 1. Try to find JSON block first
            json_match = re.search(r'\{.*?\}', response_text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    if 'equations' in data:
                        equations = data['equations']
                        if isinstance(equations, str):
                            equations = [equations]
                        return equations, True
                except:
                    pass

            # 2. Look for equation patterns
            equations = []
            lines = response_text.split('\n')
            
            for line in lines:
                line = line.strip()
                # Skip non-equation lines
                if not line or not '=' in line:
                    continue
                    
                # Clean up the line
                eq = re.sub(r'^[-*•\s]+', '', line)
                
                # Skip if it contains explanation words
                if any(word in eq.lower() for word in ['therefore', 'thus', 'hence', 'because']):
                    continue
                
                # Clean up equation
                eq = eq.strip(' ."\'')
                if '=' in eq:
                    equations.append(eq)

            return equations, bool(equations)

        except Exception as e:
            print(f"Response parsing error: {e}")
            return [], False

# --------------------------
# Enhanced Retriever
# --------------------------
class Retriever(dspy.Module):
    """FAISS-based retrieval with error handling"""
    
    def __init__(self, index_path: str, idmap_path: str):
        super().__init__()
        self.index = FaissIndexer.load(index_path, idmap_path)
        
        with open(idmap_path) as f:
            self.db = json.load(f)
        
        self.max_idx = len(self.db) - 1
    
    def forward(self, hybrid_vector, top_k: int = 5):
        try:
            # FaissIndexer.search returns (distances, results_list)
            # where results_list is a list of dicts like {'id': ..., 'metadata': {...}}
            distances, results_list = self.index.search(hybrid_vector, top_k=top_k)
            
            # Ensure distances and results_list are properly formatted
            if hasattr(distances, 'tolist'):
                distances = distances.tolist()
            
            # Handle single query case (not batched)
            if isinstance(distances, list) and len(distances) > 0 and not isinstance(distances[0], (list, tuple)):
                distances = [distances]
                results_list = [results_list]
            
            # Take the first (and only) query result
            if len(distances) > 0:
                distances = distances[0]
                results_list = results_list[0]
            
        except Exception as e:
            return dspy.Prediction(
                results=[], 
                error=f"Search failed: {str(e)}"
            )
        
        retrieved = []
        
        for dist, entry in zip(distances, results_list):
            try:
                # The 'entry' already contains the id and metadata from FaissIndexer
                text = entry.get("metadata", {}).get("text", entry.get("metadata", {}).get("problem_text", "No text available"))
                
                retrieved.append({
                    "similarity": float(dist),
                    "text": text,
                    "id": entry.get("id"),
                    "metadata": entry.get("metadata", {})
                })
            except Exception as e:
                retrieved.append({
                    "similarity": float(dist),
                    "text": f"[Error processing entry: {str(e)}]",
                    "error": str(e)
                })
        
        return dspy.Prediction(results=retrieved)


# --------------------------
# Evaluation Module
# --------------------------
class RetrievalEvaluator(dspy.Module):
    """Evaluate retrieval quality with multiple metrics"""
    
    def forward(self, query_vectors: np.ndarray, target_vectors: np.ndarray, 
               top_k: int = 5, relevance_threshold: float = 0.7):
        """
        Compute retrieval evaluation metrics.
        
        Args:
            query_vectors: NxD query embeddings
            target_vectors: MxD target embeddings
            top_k: Number of results to consider
            relevance_threshold: Similarity threshold for relevance
        """
        if len(query_vectors) == 0 or len(target_vectors) == 0:
            return dspy.Prediction(
                precision_at_k=0.0,
                mean_cosine_similarity=0.0,
                error="Empty input vectors"
            )
        
        # Compute similarities
        cos_sim = cosine_similarity(query_vectors, target_vectors)
        
        precision_scores = []
        mean_cos_scores = []
        mrr_scores = []  # Mean Reciprocal Rank
        
        for i in range(len(query_vectors)):
            # Get top-k indices
            top_indices = np.argsort(cos_sim[i])[::-1][:top_k]
            top_sim_values = cos_sim[i][top_indices]
            
            # Precision@k
            relevant_count = np.sum(top_sim_values >= relevance_threshold)
            precision = relevant_count / top_k
            precision_scores.append(precision)
            
            # Mean similarity
            mean_cos_scores.append(float(np.mean(top_sim_values)))
            
            # MRR: reciprocal rank of first relevant item
            relevant_ranks = np.where(top_sim_values >= relevance_threshold)[0]
            if len(relevant_ranks) > 0:
                mrr_scores.append(1.0 / (relevant_ranks[0] + 1))
            else:
                mrr_scores.append(0.0)
        
        return dspy.Prediction(
            precision_at_k=float(np.mean(precision_scores)),
            mean_cosine_similarity=float(np.mean(mean_cos_scores)),
            mean_reciprocal_rank=float(np.mean(mrr_scores)),
            per_query_precision=precision_scores,
            per_query_similarity=mean_cos_scores
        )


# --------------------------
# Similarity Explanation
# --------------------------
def explain_similarity(query: str, document: str, 
                      query_embedding: np.ndarray, 
                      doc_embedding: np.ndarray) -> Dict[str, Any]:
    """
    Explain why a document is similar to the query using multiple signals.
    """
    explanations = {}
    
    # Embedding cosine similarity
    cos_sim = float(cosine_similarity(
        query_embedding.reshape(1, -1),
        doc_embedding.reshape(1, -1)
    )[0][0])
    explanations['embedding_cosine_similarity'] = round(cos_sim, 4)
    
    # Keyword overlap
    try:
        vectorizer = CountVectorizer(stop_words='english', min_df=1)
        vectorizer.fit([query, document])
        qv = vectorizer.transform([query]).toarray()
        dv = vectorizer.transform([document]).toarray()
        keyword_sim = float(cosine_similarity(qv, dv)[0][0])
        explanations['keyword_overlap_score'] = round(keyword_sim, 4)
    except Exception:
        explanations['keyword_overlap_score'] = 0.0
    
    # Common tokens
    q_tokens = set(query.lower().split())
    d_tokens = set(document.lower().split())
    common = q_tokens.intersection(d_tokens)
    explanations['common_tokens'] = sorted(list(common))[:10]  # Limit to 10
    explanations['common_token_count'] = len(common)
    
    # Jaccard similarity
    jaccard = len(common) / len(q_tokens.union(d_tokens)) if q_tokens or d_tokens else 0.0
    explanations['jaccard_similarity'] = round(jaccard, 4)
    
    return explanations


# --------------------------
# Core Pipeline Modules
# --------------------------
class EquationExtractor(dspy.Module):
    def forward(self, text):
        equations = extract_equations_advanced(text)
        # Ensure we return a list of equation strings, not complex objects
        if equations and isinstance(equations, list):
            # Filter out non-string equations and convert to strings
            equation_strings = []
            for eq in equations:
                if isinstance(eq, str):
                    equation_strings.append(eq)
                elif hasattr(eq, '__str__'):
                    equation_strings.append(str(eq))
            return dspy.Prediction(equations=equation_strings)
        return dspy.Prediction(equations=[])


class Canonicalizer(dspy.Module):
    def forward(self, equations):
        if not equations:
            return dspy.Prediction(canonical=[])
        try:
            canonical_result = canonicalize_system(equations)
            # Extract the actual canonical equations from the result
            if isinstance(canonical_result, dict):
                # Get the parsed expressions (SymPy objects) instead of strings
                parsed_list = canonical_result.get('parsed', [])
                canonical = []
                for parsed_item in parsed_list:
                    if parsed_item.get('expr') is not None:
                        canonical.append(parsed_item['expr'])
                return dspy.Prediction(canonical=canonical)
            else:
                return dspy.Prediction(canonical=canonical_result)
        except Exception as e:
            return dspy.Prediction(canonical=[], error=str(e))


class StructureEncoder(dspy.Module):
    def forward(self, canonical):
        if not canonical:
            return dspy.Prediction(structure_vector=np.zeros(256))
        try:
            vec = build_structure_vector_from_parsed(canonical)
            return dspy.Prediction(structure_vector=vec)
        except Exception as e:
            return dspy.Prediction(structure_vector=np.zeros(256), error=str(e))


class TextEncoder(dspy.Module):
    def forward(self, text):
        try:
            vec = encode_texts([text], normalize=True)[0]
            return dspy.Prediction(text_vector=vec)
        except Exception as e:
            # Return zero vector on error
            return dspy.Prediction(text_vector=np.zeros(384), error=str(e))


class HybridEncoder(dspy.Module):
    def forward(self, structure_vector, text_vector):
        hybrid = np.concatenate([structure_vector, text_vector])
        return dspy.Prediction(hybrid_vector=hybrid)


# --------------------------
# Main Pipeline
# --------------------------
class SmartRetrievalPipeline(dspy.Module):
    """
    DSPy-based hybrid neuro-symbolic retrieval pipeline with:
    - Equation extraction and canonicalization
    - Hybrid embedding (structure + semantics)
    - FAISS vector search
    - Symbolic solver with verification
    - LLM fallback with reasoning
    - Comprehensive error handling
    """
    
    def __init__(self, index_path: str, idmap_path: str, llm_model=None):
        super().__init__()
        
        print("Loading DSPy Hybrid Neuro-Symbolic Retrieval System...")
        print("=" * 60)
        
        # Core modules
        self.eq_extractor = EquationExtractor()
        self.canonicalizer = Canonicalizer()
        self.structure_encoder = StructureEncoder()
        self.text_encoder = TextEncoder()
        self.hybrid_encoder = HybridEncoder()
        self.retriever = Retriever(index_path, idmap_path)
        self.index = self.retriever.index.index
        
        # Metadata
        with open(idmap_path) as f:
            self.problem_db = json.load(f)
        
        # Neuro-symbolic components
        self.sym_solver = SymbolicSolver()
        self.verifier = Verifier()
        self.llm_reasoner = LLMReasoner(llm_model)
        
        print(f"✓ System Loaded Successfully!")
        print(f"  Knowledge Base: {len(self.problem_db)} math problems")
        print(f"  Index dimension: {self.index.d}")
        if self.llm_reasoner.llm_model is not None:
            print(f"  LLM Model: CTransformers (Llama-2-7B-Chat)")
        else:
            print(f"  LLM Model: Not available")
        print()
    
    def forward(self, text: str, top_k: int = 5, explain: bool = False):
        """
        Main forward pass through the neuro-symbolic pipeline.
        """
        # Step 1: Extract equations
        eq_pred = self.eq_extractor(text)
        equations = eq_pred.equations if eq_pred.equations else self._pattern_based_extraction(text)
        
        # Step 2: Canonicalize
        can_pred = self.canonicalizer(equations)
        canonical = can_pred.canonical
        
        # Step 3: Structure encoding
        struct_pred = self.structure_encoder(canonical)
        
        # Step 4: Text encoding
        text_for_embedding = build_text_for_embedding(text, fingerprint=None)
        text_pred = self.text_encoder(text_for_embedding)
        
        # Step 5: Hybrid fusion
        hybrid_pred = self.hybrid_encoder(
            struct_pred.structure_vector, 
            text_pred.text_vector
        )
        
        # Step 6: Retrieval
        retr_pred = self.retriever(hybrid_pred.hybrid_vector, top_k=top_k)
        retrieved_results = retr_pred.results if hasattr(retr_pred, 'results') else []
        
        # Step 7: Attempt symbolic solving with canonical equations
        if canonical:
            sym_out = self.sym_solver(canonical)
            if getattr(sym_out, "success", False):
                ver = self.verifier(canonical, sym_out.solution)
                if ver.verification["ok"]:
                    return dspy.Prediction(
                        result_type="symbolic",
                        solution=sym_out.solution,
                        residuals=sym_out.residuals,
                        results=retrieved_results,
                        equations=canonical
                    )
        
        # Step 8: LLM fallback - extract equations and try symbolic solving
        try:
            llm_out = self.llm_reasoner(text, canonical, retrieved_results)
            if getattr(llm_out, "success", False) and llm_out.llm_equations:
                print(f"🔍 LLM extracted equations: {llm_out.llm_equations}")
                
                # Try symbolic solving with LLM extracted equations
                if llm_out.llm_equations:
                    sym_out_llm = self.sym_solver(llm_out.llm_equations)
                    if getattr(sym_out_llm, "success", False):
                        print(f"✅ Symbolic solver succeeded with LLM equations!")
                        return dspy.Prediction(
                            result_type="symbolic_llm",
                            solution=sym_out_llm.solution,
                            residuals=sym_out_llm.residuals,
                            results=retrieved_results,
                            equations=llm_out.llm_equations,
                            reasoning=llm_out.llm_steps
                        )
                
                # If symbolic solving failed, check if LLM provided a solution
                if llm_out.llm_solution:
                    if canonical:
                        ver2 = self.verifier(canonical, llm_out.llm_solution)
                        if ver2.verification["ok"]:
                            return dspy.Prediction(
                                result_type="llm",
                                solution=llm_out.llm_solution,
                                reasoning=llm_out.llm_steps,
                                results=retrieved_results,
                                equations=canonical
                            )
                    else:
                        # No equations to verify, trust LLM
                        return dspy.Prediction(
                            result_type="llm",
                            solution=llm_out.llm_solution,
                            reasoning=llm_out.llm_steps,
                            results=retrieved_results,
                            equations=llm_out.llm_equations
                        )
        except Exception as e:
            print(f"LLM reasoning failed: {e}")
        
        # Step 9: Unresolved - needs human intervention
        return dspy.Prediction(
            result_type="unresolved",
            results=retrieved_results,
            note="Unable to solve automatically - human review required",
            extracted_equations=equations,
            canonical_equations=canonical
        )
    
    def _pattern_based_extraction(self, text: str) -> List[str]:
        """
        Improved pattern-based fallback for equation extraction.
        """
        text_lower = text.lower()
        equations = []
        numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', text)
        
        if len(numbers) < 2:
            return equations
        
        # Distance/Speed problems
        if any(kw in text_lower for kw in ["speed", "distance", "km", "mph", "km/h"]):
            if "per" in text_lower or "/" in text:
                equations.append(f"speed = distance / time")
        
        # Cost/Price problems
        elif any(kw in text_lower for kw in ["cost", "price", "buy", "total"]):
            if "each" in text_lower:
                equations.append(f"total_cost = quantity * unit_price")
        
        # Percentage problems
        elif "%" in text or "percent" in text_lower:
            equations.append(f"result = base * (percentage / 100)")
        
        # System of equations keywords
        elif "sum" in text_lower and "difference" in text_lower:
            if len(numbers) >= 2:
                equations.extend([
                    f"x + y = {numbers[0]}",
                    f"x - y = {numbers[1]}"
                ])
        
        return equations
    
    def evaluate_retrieval_quality(self, queries: List[str], 
                                   top_k: int = 5, 
                                   sample_size: int = 1000):
        """
        Evaluate retrieval quality efficiently using sampling.
        """
        if not queries:
            print("⚠️ No queries provided")
            return None
        
        print(f"Evaluating on {len(queries)} queries...")
        
        # Get query vectors
        query_vectors = []
        for q in queries:
            # Step 1: Extract equations
            eq_pred = self.eq_extractor(q)
            equations = eq_pred.equations if eq_pred.equations else self._pattern_based_extraction(q)
            
            # Step 2: Canonicalize
            can_pred = self.canonicalizer(equations)
            canonical = can_pred.canonical
            
            # Step 3: Structure encoding
            struct_pred = self.structure_encoder(canonical)
            
            # Step 4: Text encoding
            text_for_embedding = build_text_for_embedding(q, fingerprint=None)
            text_pred = self.text_encoder(text_for_embedding)
            
            # Step 5: Hybrid fusion
            hybrid_pred = self.hybrid_encoder(
                struct_pred.structure_vector, 
                text_pred.text_vector
            )
            query_vectors.append(hybrid_pred.hybrid_vector)
        
        query_vectors = np.vstack(query_vectors)
        
        # Sample target vectors efficiently
        n_total = self.index.ntotal
        sample_size = min(sample_size, n_total)
        sampled_indices = np.random.choice(n_total, sample_size, replace=False)
        
        target_vectors = np.vstack([
            self.index.reconstruct(int(i)) 
            for i in sampled_indices
        ])
        
        evaluator = RetrievalEvaluator()
        metrics = evaluator(query_vectors, target_vectors, top_k=top_k)
        
        print(f"✓ Evaluation complete")
        print(f"  Precision@{top_k}: {metrics.precision_at_k:.4f}")
        print(f"  Mean Cosine Similarity: {metrics.mean_cosine_similarity:.4f}")
        print(f"  Mean Reciprocal Rank: {metrics.mean_reciprocal_rank:.4f}")
        
        return metrics

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
class TopicBandit:
    """
    Manages the 'Weak Spots' using a Weighted Bandit Algorithm.
    - High Weight = Weak Spot (High probability of appearing)
    - Low Weight = Mastered (Low probability of appearing)
    """
    def __init__(self, topics: List[str]):
        # Initialize all topics with equal weight (1.0)
        self.weights = {topic: 1.0 for topic in topics}
        self.min_weight = 0.1  # Don't let topics disappear completely
        self.max_weight = 5.0  # Cap the difficulty focus

    def select_topics(self, k=10) -> List[str]:
        """Select k topics based on current weights (Probabilistic Sampling)"""
        topics = list(self.weights.keys())
        weights = list(self.weights.values())
        
        # Weighted random selection with replacement
        selected = random.choices(topics, weights=weights, k=k)
        return selected

    def update(self, topic: str, is_correct: bool):
        """
        Reinforcement Update Step:
        - Correct (Reward) -> Decrease weight (Exploit mastery)
        - Incorrect (Penalty) -> Increase weight (Explore/Fix weakness)
        """
        current = self.weights[topic]
        
        if is_correct:
            # Positive Reward: User knows this. Reduce frequency.
            new_weight = max(self.min_weight, current * 0.7)
        else:
            # Negative Reward: Weak spot identified. Increase frequency.
            new_weight = min(self.max_weight, current * 1.5)
            
        self.weights[topic] = new_weight

# ---------------------------------------------------------
# 4. MAIN FORUM CONTROLLER
# ---------------------------------------------------------
class PracticeForum:
    """
    Main Controller for the Adaptive Practice Session.
    Uses existing SymbolicSolver to grade user equations.
    """
    def __init__(self):
        self.bank = QuestionBank()
        self.bandit = TopicBandit(self.bank.all_topics)
        self.solver = SymbolicSolver()
        self.verifier = Verifier()

    def grade_submission(self, user_equations: List[str], ground_truth_numeric: float) -> bool:
        """
        Determines if the User's Equation results in the correct answer.
        """
        # 1. Solve User's Equation using your SymbolicSolver
        solve_result = self.solver(user_equations)
        
        if not solve_result.success:
            return False

        # 2. Compare User's Solution Value to Ground Truth Value
        user_sol = solve_result.solution
        
        # Check if any variable in the solution matches the ground truth
        if user_sol:
            for val in user_sol.values():
                if abs(float(val) - float(ground_truth_numeric)) < 0.1: # Tolerance for rounding
                    return True
        
        return False

    def run_session(self):
        """Runs a 10-question adaptive session"""
        print("\n STARTING ADAPTIVE PRACTICE SESSION")
        print("="*60)
        
        # 1. Bandit selects topics based on weights
        session_topics = self.bandit.select_topics(k=5) # Reduced to 5 for demo brevity
        
        score = 0
        
        for i, topic in enumerate(session_topics, 1):
            q_data = self.bank.get_question(topic)
            question = q_data['q']
            gt_text = q_data['solution_text']
            gt_val = q_data['ground_truth_numeric']
            
            print(f"\n[{i}/5] Topic: {topic.upper().replace('_', ' ')}")
            print(f"Question: {question}")
            
            # --- SIMULATE USER INPUT (For demonstration) ---
            # To demonstrate the bandit, we will simulate:
            # - Mastery in 'Algebra' & 'Physics' (Correct answers)
            # - Weakness in 'Geometry' & 'Ratios' (Wrong answers)
            
            user_input = []
            if topic in ['algebra_arithmetic', 'physics_kinematics']:
                # User generates a correct equation (simulated)
                user_input = [f"x = {gt_val}"] 
                print(f"   👤 User Submission: {user_input}")
            else:
                # User generates a wrong equation
                user_input = ["x = 0"]
                print(f" User Submission: {user_input}")

            # --- GRADING ---
            is_correct = self.grade_submission(user_input, gt_val)
            
            if is_correct:
                print("   ✅ System Verdict: CORRECT")
                score += 1
            else:
                print("   System Verdict: INCORRECT")
                print(f"   (Correct Solution: {gt_text})")
            
            # --- REINFORCEMENT STEP ---
            self.bandit.update(topic, is_correct)
            
        print("="*60)
        print(f" Session Complete. Score: {score}/5")
        print("\nADAPTIVE WEIGHTS FOR NEXT SESSION (The Agent's Memory):")
        for t, w in self.bandit.weights.items():
            status = "Weak Spot (More Freq)" if w > 1.0 else "Mastered (Less Freq)"
            print(f"   - {t.ljust(25)}: {w:.2f} [{status}]")


# =============================================================================
#  This adds the "Adaptive Practice Mode" feature to your existing app.
# =============================================================================

import random
import csv
import io

# 1. THE PRACTICE DATASET
# ---------------------------------------------------------
# This acts as your database of questions.
RAW_DATASET = """problem_id,problem_text,solution_text
1,A car covers 150 km in 3 hours. What is its speed?,Speed = Distance / Time = 150 / 3 = 50 km/hr
2,The sum of two numbers is 40 and their difference is 10. Find the numbers.,"Let x + y = 40, x - y = 10 -> x = 25, y = 15"
3,"If a book costs $12 and you buy 5 books, how much do you spend?",Total cost = 12 * 5 = $60
4,A rectangle has a length of 10 cm and width of 6 cm. What is its area?,Area = Length * Width = 10 * 6 = 60 cm^2
5,"If 40% of a number is 80, what is the number?",Let x be the number: 0.4x = 80 -> x = 200
6,A train travels at 60 km/h. How far does it travel in 2.5 hours?,Distance = Speed * Time = 60 * 2.5 = 150 km
7,The perimeter of a square is 36 cm. What is the length of each side?,Perimeter = 4 * side -> 36 = 4s -> s = 9 cm
8,"If 3 pens cost $6, how much do 8 pens cost?",Cost per pen = 6/3 = $2 -> 8 pens = 8 * 2 = $16
9,The sum of three consecutive numbers is 51. Find the numbers.,"Let x, x+1, x+2 be the numbers: x + (x+1) + (x+2) = 51 -> x = 16. Numbers are 16, 17, 18"
10,A store offers a 25% discount on a $80 item. What is the sale price?,Discount = 0.25 * 80 = $20 -> Sale price = 80 - 20 = $60
"""

# 2. QUESTION BANK (The Librarian)
# ---------------------------------------------------------
class QuestionBank:
    """Categorizes questions so the Agent knows what topic is what."""
    def __init__(self):
        self.db = {} 
        self.all_topics = []
        self._load_and_categorize_dataset()

    def _categorize_problem(self, text):
        # Simple keyword matching to find the topic
        text = text.lower()
        if any(w in text for w in ['area', 'perimeter', 'volume', 'triangle', 'square']): return 'geometry'
        if any(w in text for w in ['ratio', 'percentage', 'discount', 'cost', 'price']): return 'ratios_percentages'
        if any(w in text for w in ['speed', 'distance', 'time', 'km']): return 'physics'
        if any(w in text for w in ['x', 'sum', 'difference', 'number']): return 'algebra'
        return 'general'

    def _extract_ground_truth(self, solution_text):
        # Extracts the number 50.0 from "Speed = 50 km/hr"
        import re
        matches = re.findall(r"[-+]?\d*\.\d+|\d+", solution_text)
        return float(matches[-1]) if matches else 0.0

    def _load_and_categorize_dataset(self):
        reader = csv.DictReader(io.StringIO(RAW_DATASET))
        for row in reader:
            topic = self._categorize_problem(row['problem_text'])
            gt_val = self._extract_ground_truth(row['solution_text'])
            
            if topic not in self.db: self.db[topic] = []
            self.db[topic].append({
                "q": row['problem_text'],
                "solution_text": row['solution_text'],
                "ground_truth_numeric": gt_val
            })
        self.all_topics = list(self.db.keys())
        print(f"[DATA] Loaded {sum(len(v) for v in self.db.values())} questions.")

    def get_question(self, topic):
        if topic not in self.db: return None
        return random.choice(self.db[topic])

# 3. TOPIC BANDIT (The Adaptive Agent)
# ---------------------------------------------------------
class TopicBandit:
    """
    Uses 'Weighted Softmax' to pick questions.
    If you fail a topic, its weight goes UP, so you see it more often.
    """
    def __init__(self, topics):
        self.weights = {topic: 1.0 for topic in topics}
        self.min_weight = 0.1
        self.max_weight = 5.0

    def select_topics(self, k=5):
        # Picks k topics based on their weights
        topics = list(self.weights.keys())
        weights = list(self.weights.values())
        return random.choices(topics, weights=weights, k=k)

    def update(self, topic, is_correct):
        current = self.weights[topic]
        if is_correct:
            # Reward: Reduce weight (Show less often)
            self.weights[topic] = max(self.min_weight, current * 0.7)
        else:
            # Penalty: Increase weight (Show MORE often - Weak Spot)
            self.weights[topic] = min(self.max_weight, current * 1.5)

import time

class PracticeForum:
    def __init__(self):
        self.bank = QuestionBank()
        self.bandit = TopicBandit(self.bank.all_topics)
        
        # Connect to existing solver
        self.solver = SymbolicSolver() 

    def grade_submission(self, user_equations, ground_truth_numeric):
        """
        Uses the SymbolicSolver to check if the User's Equation 
        mathematically equals the Ground Truth.
        """
        # 1. Solve the USER'S equation
        solve_result = self.solver(user_equations)
        
        if not solve_result.success: return False
        
        # 2. Check if the result matches the answer key
        if solve_result.solution:
            for val in solve_result.solution.values():
                if abs(float(val) - float(ground_truth_numeric)) < 0.1:
                    return True
        return False

    def run_iterative_campaign(self, num_sessions=3, questions_per_session=5):
        """
        Runs multiple sessions back-to-back to demonstrate ADAPTATION.
        """
        print(f"\n🚀 STARTING ITERATIVE CAMPAIGN ({num_sessions} Sessions)")
        print("Objective: Watch 'Algebra' frequency increase as you fail it.")
        
        for session_num in range(1, num_sessions + 1):
            print(f"\n{'='*60}")
            print(f"📅 SESSION {session_num} (Generating Worksheet...)")
            print(f"{'='*60}")
            
            # 1. VISUALIZE CURRENT WEIGHTS (Before Session)
            print("[DEBUG] Current Topic Weights (Probability of appearing):")
            total_weight = sum(self.bandit.weights.values())
            for t, w in self.bandit.weights.items():
                prob = (w / total_weight) * 100
                status = "🔴 WEAK" if w > 1.0 else "🟢 STRONG" if w < 1.0 else "⚪ NEUTRAL"
                print(f"   - {t.ljust(20)}: {w:.2f} ({prob:.1f}%) [{status}]")
            
            # 2. SELECT TOPICS
            session_topics = self.bandit.select_topics(k=questions_per_session)
            
            # Count distribution for this session
            topic_counts = {t: session_topics.count(t) for t in self.bandit.weights.keys()}
            print(f"\n[WORKSHEET] Question Distribution for Session {session_num}:")
            for t, count in topic_counts.items():
                if count > 0:
                    bar = "█" * count
                    print(f"   - {t.ljust(20)}: {count} {bar}")
            print("-" * 60)
            
            # 3. RUN THE QUESTIONS
            score = 0
            for i, topic in enumerate(session_topics, 1):
                q_data = self.bank.get_question(topic)
                if not q_data: continue
                
                print(f"\n   Q{i} [{topic.upper()}]: {q_data['q']}")
                
                # --- SIMULATION LOGIC ---
                # We Simulate FAILURE in 'algebra' to force the bandit to adapt.
                # We Simulate SUCCESS in everything else.
                if topic == 'algebra':
                    user_input = ["x = 0"] # Wrong
                    print(f"      👤 User Input: x = 0 (Simulated Wrong)")
                else:
                    user_input = [f"x = {q_data['ground_truth_numeric']}"] # Correct
                    print(f"      👤 User Input: x = {q_data['ground_truth_numeric']} (Simulated Correct)")

                # Grading & Update
                is_correct = self.grade_submission(user_input, q_data['ground_truth_numeric'])
                self.bandit.update(topic, is_correct)
                
                if is_correct: score += 1
                
            print(f"\n   🏁 Session Score: {score}/{questions_per_session}")
            print(f"   (Updating weights based on performance...)")
            time.sleep(1) # Pause for dramatic effect

        print("\n" + "="*60)
        print("🎓 CAMPAIGN FINISHED")
        print("Notice how 'Algebra' weight increased and 'Geometry' decreased?")
        print("Notice how Session 3 had MORE Algebra questions than Session 1?")

# =============================================================================
#  MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("🚀 Select Mode:")
    print("1. Standard Pipeline Test (Original)")
    print("2. Adaptive Practice Forum (Single Session)")
    print("3. Iterative Campaign Mode (Watch Adaptation)")
    
    choice = input("Enter 1, 2, or 3: ").strip()
    
    if choice == "1":
        print("\n--- Running Standard Pipeline ---")
        # pipeline = SmartRetrievalPipeline("path/to/index", "path/to/idmap")
        print("Standard test complete (Mock).")
        
    elif choice == "2":
        print("\n--- Running Adaptive Practice Forum ---")
        forum = PracticeForum()
        # Uses the old run_session method if you kept it, or call the new one with 1 session
        forum.run_iterative_campaign(num_sessions=1)
        
    elif choice == "3":
        print("\n--- Running Iterative Campaign Mode ---")
        forum = PracticeForum()
        forum.run_iterative_campaign(num_sessions=3)
        
    else:
        print("Invalid choice. Exiting.")