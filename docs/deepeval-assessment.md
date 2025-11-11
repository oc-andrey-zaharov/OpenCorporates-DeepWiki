# DeepEval Assessment for OpenCorporates DeepWiki

**Date**: January 2025  
**Purpose**: Evaluate DeepEval's suitability for testing LLM components and RAG-specific LLM parts in the DeepWiki application

## Executive Summary

**DeepEval is an EXCELLENT fit** for testing this application. It provides comprehensive RAG evaluation metrics, unit-test-like integration, and supports both LLM generation evaluation and RAG pipeline testing. The framework aligns well with DeepWiki's architecture and testing needs.

**Recommendation**: ✅ **Proceed with DeepEval integration**

---

## Application Context

OpenCorporates DeepWiki is a Python application that:

- **Generates Wikipedia-style documentation** from code repositories
- **Uses RAG (Retrieval-Augmented Generation)** to analyze code and generate wiki pages
- **Has multiple LLM components**:
  - RAG pipeline (`api/services/rag.py`) - retrieves code context and generates responses
  - Chat completion (`api/core/chat.py`) - handles streaming LLM responses
  - Wiki generation - creates structured documentation from repository code
- **Supports multiple providers**: Google Gemini, OpenAI, OpenRouter, AWS Bedrock, Ollama
- **Has existing test infrastructure**: pytest-based unit and integration tests

**Key Testing Requirements:**

1. Evaluate LLM generation quality (accuracy, relevance, completeness)
2. Evaluate RAG retrieval quality (context relevance, precision, recall)
3. Ensure generated documentation is faithful to source code
4. Test wiki-specific quality metrics (structure, clarity, coverage)
5. Support CI/CD integration
6. Enable iterative prompt refinement

---

## DeepEval Capabilities Assessment

### ✅ 1. RAG-Specific Metrics (Perfect Fit)

DeepEval provides comprehensive RAG evaluation metrics that directly address DeepWiki's needs:

#### **Retriever Metrics** (for code retrieval quality)

- **`ContextualRelevancyMetric`**: Evaluates if retrieved code context is relevant to the query
  - **Use Case**: Ensure retrieved code snippets are relevant to wiki generation queries
  - **Example**: Test if query "Generate wiki for repository" retrieves relevant code files

- **`ContextualPrecisionMetric`**: Measures precision of retrieved context
  - **Use Case**: Ensure retrieved code chunks are precise and not overly broad
  - **Example**: Verify that retrieved code sections match the specific query intent

- **`ContextualRecallMetric`**: Measures recall of relevant context
  - **Use Case**: Ensure important code sections aren't missed during retrieval
  - **Example**: Verify that all relevant API functions are retrieved for documentation

#### **Generator Metrics** (for LLM output quality)

- **`FaithfulnessMetric`**: Detects hallucinations and ensures output is grounded in context
  - **Use Case**: **CRITICAL** - Ensure generated wiki documentation accurately reflects repository code
  - **Example**: Verify that generated API documentation matches actual code implementation

- **`AnswerRelevancyMetric`**: Evaluates relevance of generated output to the input query
  - **Use Case**: Ensure generated wiki pages are relevant to the repository query
  - **Example**: Test if wiki generation query produces relevant documentation

#### **End-to-End RAG Metrics**

- **`RagasMetric`**: Wrapper for RAGAS metrics (comprehensive RAG evaluation)
  - **Use Case**: Comprehensive evaluation combining retrieval and generation quality

**Integration Example for DeepWiki:**

```python
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric
)
from deepeval.test_case import LLMTestCase
from deepeval import evaluate

# Test wiki generation with RAG
test_case = LLMTestCase(
    input="Generate wiki documentation for repository X",
    actual_output=generated_wiki_content,
    retrieval_context=retrieved_code_contexts  # From RAG pipeline
)

metrics = [
    FaithfulnessMetric(threshold=0.7),  # Must be grounded in code
    AnswerRelevancyMetric(threshold=0.8),  # Must be relevant
    ContextualRelevancyMetric(threshold=0.7),  # Retrieved code must be relevant
]

evaluate([test_case], metrics)
```

### ✅ 2. LLM Evaluation Metrics (Excellent Fit)

DeepEval provides 40+ built-in metrics for LLM evaluation:

#### **Standard LLM Metrics**

- **`GEval`**: Criteria-based evaluation mimicking human judgment
  - **Use Case**: Custom wiki-specific quality metrics
  - **Example**: Evaluate wiki documentation depth, structure, clarity

- **`SummarizationMetric`**: Evaluates summarization quality
  - **Use Case**: Perfect for evaluating wiki page summaries and descriptions
  - **Example**: Test if code summaries are clear and comprehensive

#### **Custom Metrics Support**

DeepEval supports custom metrics using `GEval` for wiki-specific criteria:

```python
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams

wiki_depth_metric = GEval(
    name="WikiDepth",
    criteria=(
        "Evaluate wiki documentation depth: "
        "1) Coverage of code structure and APIs, "
        "2) Inclusion of usage examples, "
        "3) Clarity of explanations, "
        "4) Proper section organization"
    ),
    evaluation_params=[
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.CONTEXT
    ],
    threshold=0.75
)

wiki_structure_metric = GEval(
    name="WikiStructure",
    criteria=(
        "Evaluate wiki documentation structure: "
        "1) Proper markdown formatting, "
        "2) Clear section headers, "
        "3) Code examples are properly formatted, "
        "4) Links and references are correct"
    ),
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.8
)
```

### ✅ 3. Unit-Test-Like Integration (Perfect for CI/CD)

DeepEval's pytest integration makes it ideal for CI/CD:

```python
import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric

def test_wiki_generation_faithfulness():
    """Test that generated wiki is faithful to source code."""
    test_case = LLMTestCase(
        input="Generate wiki for repository X",
        actual_output=generated_wiki,
        retrieval_context=retrieved_code_contexts
    )
    
    assert_test(
        test_case,
        [FaithfulnessMetric(threshold=0.7)]
    )

# Run with: deepeval test run test_wiki.py
# Or: pytest test_wiki.py
```

**Benefits:**

- ✅ Integrates seamlessly with existing pytest infrastructure
- ✅ Can run in parallel (`deepeval test run -n 4`)
- ✅ CI/CD friendly (exit codes, test reports)
- ✅ Fast local execution

### ✅ 4. Component-Level Tracing (Advanced Feature)

DeepEval supports component-level evaluation using `@observe` decorator:

```python
from deepeval.tracing import observe, update_current_span
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

@observe(metrics=[FaithfulnessMetric(), AnswerRelevancyMetric()])
def generate_wiki_page(repo_context: str, query: str) -> str:
    """Wiki generation component - evaluated independently"""
    # Your wiki generation logic
    wiki_content = your_llm_generation(repo_context, query)
    
    update_current_span(
        test_case=LLMTestCase(
            input=query,
            actual_output=wiki_content,
            retrieval_context=[repo_context]
        )
    )
    return wiki_content

@observe  # Traced but not evaluated
def retrieve_code_context(query: str) -> list:
    """RAG retriever - traced for debugging"""
    # Your retrieval logic
    context = your_retriever(query)
    update_current_span(retrieval_context=context, query=query)
    return context
```

**Benefits:**

- ✅ Isolate evaluation to specific components (generator vs retriever)
- ✅ Debug individual components
- ✅ Track performance across components

### ✅ 5. Human Feedback Support (Optional)

DeepEval integrates with Confident AI platform for human feedback:

- **Dashboard**: Visual interface for team scoring
- **Custom Annotations**: Human reviewers can add feedback
- **G-Eval**: Human-like judgment scoring
- **Threshold-based**: Pass/fail evaluation

**Note**: This requires Confident AI account (free tier available), but DeepEval works standalone without it.

### ✅ 6. Feedback Loops for Prompt Refinement

DeepEval supports iterative prompt refinement:

- **Log evals to datasets**: Track evaluation results over time
- **Traces and debugging**: Analyze failures to improve prompts
- **A/B testing**: Compare different prompt variants
- **Auto-feed low scores**: Use evaluation results to refine prompts

---

## Integration Points with DeepWiki

### 1. RAG Pipeline (`api/services/rag.py`)

**Current Implementation:**

- `RAG` class handles retrieval and generation
- `prepare_retriever()` sets up code embeddings
- `call()` retrieves documents and generates responses

**DeepEval Integration:**

```python
# api/services/evaluation.py
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualRelevancyMetric
)
from deepeval.test_case import LLMTestCase
from deepeval import evaluate

class WikiEvaluator:
    def __init__(self):
        self.metrics = [
            FaithfulnessMetric(threshold=0.7, model="gpt-4"),
            AnswerRelevancyMetric(threshold=0.8, model="gpt-4"),
            ContextualRelevancyMetric(threshold=0.7, model="gpt-4"),
        ]
    
    def evaluate_wiki_generation(
        self,
        query: str,
        generated_wiki: str,
        retrieved_context: list
    ):
        test_case = LLMTestCase(
            input=query,
            actual_output=generated_wiki,
            retrieval_context=[doc.text for doc in retrieved_context]
        )
        return evaluate([test_case], self.metrics)
```

**Integration in `api/services/rag.py`:**

```python
# After RAG generation
if config.get("evaluation.enabled", False):
    from api.services.evaluation import WikiEvaluator
    evaluator = WikiEvaluator()
    results = evaluator.evaluate_wiki_generation(
        query=query,
        generated_wiki=rag_answer.answer,
        retrieved_context=retrieved_documents[0].documents
    )
    logger.info(f"Evaluation results: {results}")
```

### 2. Chat Completion (`api/core/chat.py`)

**Current Implementation:**

- `generate_chat_completion_core()` handles streaming LLM responses
- Uses RAG for context retrieval
- Supports multiple providers

**DeepEval Integration:**

```python
# Add evaluation after generation
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase

def evaluate_chat_response(
    query: str,
    response: str,
    context: str
):
    test_case = LLMTestCase(
        input=query,
        actual_output=response,
        retrieval_context=[context] if context else []
    )
    
    metrics = [
        AnswerRelevancyMetric(threshold=0.7),
        FaithfulnessMetric(threshold=0.7)
    ]
    
    return evaluate([test_case], metrics)
```

### 3. Test Suite Integration

**Existing Test Structure:**

- `tests/unit/` - Unit tests
- `tests/integration/` - Integration tests

**Add DeepEval Tests:**

```python
# tests/integration/test_rag_evaluation.py
import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
from api.services.rag import RAG

@pytest.fixture
def rag_instance():
    rag = RAG(provider="google", model="gemini-2.0-flash-exp")
    rag.prepare_retriever("test_repo_url", type="github")
    return rag

def test_rag_faithfulness(rag_instance):
    """Test that RAG responses are faithful to retrieved context."""
    query = "What does this repository do?"
    retrieved_docs = rag_instance(query)
    
    # Generate response (simplified - actual implementation would use generator)
    actual_output = "Generated response based on retrieved docs"
    
    test_case = LLMTestCase(
        input=query,
        actual_output=actual_output,
        retrieval_context=[doc.text for doc in retrieved_docs[0].documents]
    )
    
    assert_test(
        test_case,
        [FaithfulnessMetric(threshold=0.7)]
    )
```

---

## Comparison with Existing Recommendations

Based on `docs/llm-evaluation-framework-recommendations.md`, DeepEval was ranked #2 (after RAGAS). Here's how it compares:

| Feature | DeepEval | RAGAS (Ranked #1) | Fit for DeepWiki |
|---------|----------|-------------------|------------------|
| **RAG Focus** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Both excellent |
| **Ease of Integration** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **DeepEval wins** |
| **Unit-Test API** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | **DeepEval wins** |
| **CI/CD Friendly** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | **DeepEval wins** |
| **40+ Metrics** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **DeepEval wins** |
| **Component Tracing** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | **DeepEval wins** |
| **Human Feedback** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Tie |
| **Python Support** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Tie |

**Key Advantages of DeepEval:**

1. **Simpler Integration**: Unit-test-like API vs RAGAS's dataset-based approach
2. **Better CI/CD**: Pytest integration, parallel execution
3. **More Metrics**: 40+ built-in metrics vs RAGAS's RAG-focused set
4. **Component Tracing**: Advanced debugging capabilities
5. **No Dataset Dependency**: Works directly with test cases vs requiring HuggingFace datasets

**When RAGAS Might Be Better:**

- If you need RAGAS-specific training capabilities
- If you prefer dataset-based evaluation workflows
- If you need gradient-free prompt optimization

**Recommendation**: DeepEval is actually **better suited** for DeepWiki due to its simpler integration and CI/CD friendliness, even though RAGAS was ranked #1 in the general recommendations.

---

## Implementation Roadmap

### Phase 1: Basic Integration (Week 1)

1. **Install DeepEval**

   ```bash
   poetry add deepeval
   ```

2. **Create Evaluation Service**
   - Create `api/services/evaluation.py`
   - Implement `WikiEvaluator` class with basic metrics
   - Add configuration for evaluation thresholds

3. **Add Basic Tests**
   - Create `tests/integration/test_rag_evaluation.py`
   - Test faithfulness and relevancy metrics
   - Integrate with existing pytest infrastructure

### Phase 2: Custom Metrics (Week 2)

1. **Create Wiki-Specific Metrics**
   - `WikiDepthMetric` - Coverage and completeness
   - `WikiStructureMetric` - Markdown formatting and organization
   - `CodeAccuracyMetric` - Code examples accuracy

2. **Add to Test Suite**
   - Expand test coverage
   - Add tests for different repository types
   - Test with different LLM providers

### Phase 3: CI/CD Integration (Week 3)

1. **Add to CI Pipeline**
   - Integrate with GitHub Actions / CI
   - Add evaluation step to wiki generation workflow
   - Set up test reporting

2. **Component-Level Tracing** (Optional)
   - Add `@observe` decorators to key components
   - Enable detailed tracing for debugging
   - Set up evaluation dashboard (optional)

### Phase 4: Iterative Refinement (Ongoing)

1. **Use Evaluation Results**
   - Refine prompts based on low scores
   - Track improvements over time
   - A/B test different prompt strategies

---

## Code Examples

### Example 1: Basic RAG Evaluation

```python
# api/services/evaluation.py
from deepeval import evaluate
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualRelevancyMetric
)
from deepeval.test_case import LLMTestCase
from typing import List

class WikiEvaluator:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.metrics = [
            FaithfulnessMetric(threshold=0.7, model=model, include_reason=True),
            AnswerRelevancyMetric(threshold=0.8, model=model, include_reason=True),
            ContextualRelevancyMetric(threshold=0.7, model=model, include_reason=True),
        ]
    
    def evaluate_wiki_generation(
        self,
        query: str,
        generated_wiki: str,
        retrieved_context: List[str]
    ):
        """Evaluate wiki generation quality."""
        test_case = LLMTestCase(
            input=query,
            actual_output=generated_wiki,
            retrieval_context=retrieved_context
        )
        
        results = evaluate([test_case], self.metrics)
        return results
```

### Example 2: Custom Wiki Metrics

```python
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams

class WikiDepthMetric(GEval):
    def __init__(self, threshold: float = 0.75):
        super().__init__(
            name="WikiDepth",
            criteria=(
                "Evaluate wiki documentation depth and completeness: "
                "1) Coverage of code structure, APIs, and key functions, "
                "2) Inclusion of usage examples and code snippets, "
                "3) Clarity and comprehensiveness of explanations, "
                "4) Proper section organization and navigation"
            ),
            evaluation_params=[
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.CONTEXT
            ],
            threshold=threshold,
            strict_mode=True
        )

class WikiStructureMetric(GEval):
    def __init__(self, threshold: float = 0.8):
        super().__init__(
            name="WikiStructure",
            criteria=(
                "Evaluate wiki documentation structure and formatting: "
                "1) Proper markdown formatting (headers, lists, code blocks), "
                "2) Clear section headers and hierarchy, "
                "3) Code examples are properly formatted with syntax highlighting, "
                "4) Links and references are correct and functional"
            ),
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=threshold,
            strict_mode=True
        )
```

### Example 3: Integration Test

```python
# tests/integration/test_wiki_evaluation.py
import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
from api.services.rag import RAG
from api.services.evaluation import WikiEvaluator, WikiDepthMetric

@pytest.fixture
def rag_instance():
    """Create RAG instance for testing."""
    rag = RAG(provider="google", model="gemini-2.0-flash-exp")
    # Use a test repository
    rag.prepare_retriever("test_repo", type="github")
    return rag

@pytest.fixture
def evaluator():
    """Create evaluator instance."""
    return WikiEvaluator(model="gpt-4o-mini")

def test_wiki_generation_faithfulness(rag_instance, evaluator):
    """Test that generated wiki is faithful to source code."""
    query = "Generate comprehensive wiki documentation for this repository"
    
    # Retrieve context
    retrieved_docs = rag_instance(query)
    context = [doc.text for doc in retrieved_docs[0].documents]
    
    # Generate wiki (simplified - actual would use generator)
    # In real implementation, this would come from the generator component
    actual_output = "Generated wiki content..."
    
    test_case = LLMTestCase(
        input=query,
        actual_output=actual_output,
        retrieval_context=context
    )
    
    assert_test(
        test_case,
        [
            FaithfulnessMetric(threshold=0.7),
            AnswerRelevancyMetric(threshold=0.8)
        ]
    )

def test_wiki_depth_metric(rag_instance, evaluator):
    """Test wiki documentation depth and completeness."""
    query = "Generate wiki documentation"
    retrieved_docs = rag_instance(query)
    context = [doc.text for doc in retrieved_docs[0].documents]
    actual_output = "Generated wiki content..."
    
    test_case = LLMTestCase(
        input=query,
        actual_output=actual_output,
        retrieval_context=context
    )
    
    wiki_depth = WikiDepthMetric(threshold=0.75)
    assert_test(test_case, [wiki_depth])
```

---

## Potential Challenges and Solutions

### Challenge 1: Cost of Evaluation LLM Calls

**Issue**: DeepEval uses LLMs to evaluate outputs, which incurs API costs.

**Solutions**:

- Use cheaper models for evaluation (e.g., `gpt-4o-mini` instead of `gpt-4`)
- Cache evaluation results for identical inputs
- Run evaluations selectively (not on every generation)
- Use local models (Ollama) for evaluation when possible

### Challenge 2: Evaluation Latency

**Issue**: LLM-based evaluation adds latency to wiki generation.

**Solutions**:

- Run evaluations asynchronously (don't block wiki generation)
- Use evaluation in CI/CD rather than real-time
- Batch evaluations for multiple wiki pages
- Use faster evaluation models

### Challenge 3: Threshold Tuning

**Issue**: Finding the right thresholds for pass/fail criteria.

**Solutions**:

- Start with conservative thresholds (0.7-0.8)
- Use evaluation results to calibrate thresholds
- Track false positive/negative rates
- Adjust thresholds based on use case requirements

---

## Conclusion

**DeepEval is an EXCELLENT fit** for OpenCorporates DeepWiki because:

1. ✅ **Comprehensive RAG Metrics**: Perfect for evaluating code-to-documentation generation
2. ✅ **Simple Integration**: Unit-test-like API integrates seamlessly with existing pytest infrastructure
3. ✅ **CI/CD Friendly**: Built-in pytest support, parallel execution, test reporting
4. ✅ **40+ Built-in Metrics**: Covers all evaluation needs without custom implementation
5. ✅ **Component-Level Tracing**: Advanced debugging capabilities
6. ✅ **Custom Metrics Support**: Easy to create wiki-specific evaluation criteria
7. ✅ **Active Development**: Well-maintained with good documentation

**Recommendation**: ✅ **Proceed with DeepEval integration**

**Next Steps**:

1. Install DeepEval: `poetry add deepeval`
2. Create `api/services/evaluation.py` with basic evaluator
3. Add integration tests in `tests/integration/test_rag_evaluation.py`
4. Integrate evaluation into wiki generation pipeline (optional, async)
5. Add custom wiki-specific metrics

---

## References

- **DeepEval Documentation**: <https://docs.confident-ai.com/>
- **DeepEval GitHub**: <https://github.com/confident-ai/deepeval>
- **Context7 Documentation**: Accessed via Context7 MCP server
- **Existing Recommendations**: `docs/llm-evaluation-framework-recommendations.md`
