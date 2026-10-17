"""
LLM client for Legal Risk & Compliance AI System

Handles communication with the Groq LLM service with proper error handling,
timeout management, and retry logic. Supports mock mode for testing.
"""

import logging
import sys
from pathlib import Path
from ..config import LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT, LLM_MAX_RETRIES, MOCK_LLM_ENABLED

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from groq_client import GroqError, groq_chat_completion

logger = logging.getLogger(__name__)

# =====================================================================
# ANTI-HALLUCINATION PROMPT ENGINEERING
# =====================================================================
# This prompt is designed to minimize hallucinations through:
# 1. Chain-of-thought (explicit reasoning)
# 2. Confidence requirements
# 3. Uncertainty acknowledgment
# 4. Citation preferences
# 5. Structured output format
# =====================================================================

ANTI_HALLUCINATION_PROMPT = """You are a legal information assistant. When answering legal questions:

CRITICAL REQUIREMENTS:
1. ACCURACY: Only provide information you are confident is accurate.
2. UNCERTAINTY: Always express uncertainty using "may", "might", "could", "often", "typically", "generally"
3. DISCLAIMERS: Start with "This is general legal information, not legal advice."
4. CONFIDENCE: Include phrases like "subject to jurisdiction", "may vary by location", "generally speaking"
5. CITATIONS: Reference specific law sections, statutes, or regulations when applicable
6. REASONING: Show your thinking - explain WHY before answering

FORBIDDEN:
- DO NOT make up specific case names or statute numbers
- DO NOT use absolute language like "always", "will", "must" without qualification
- DO NOT cite specific laws unless you are very confident they exist
- DO NOT provide definitive legal conclusions - these require professional review

RESPONSE STRUCTURE:
1. Start with a disclaimer
2. Provide general principles (use cautious language)
3. Explain what TYPICALLY happens
4. List important VARIABLES that affect the answer
5. STRONGLY recommend consulting a lawyer

Remember: It's better to say "I'm not sure" than to make something up.

Now answer this question with appropriate caution and confidence-qualifying language:

"""

# Mock responses for testing without LLM
MOCK_RESPONSES = {
    "contract": """A contract typically becomes binding when all parties agree to its terms. Key things to look for when signing:

1. **Party Identification**: Ensure all parties are correctly identified with legal names and signatures.

2. **Terms and Conditions**: Carefully review all terms, conditions, and obligations you're committing to.

3. **Consideration**: Verify there's adequate consideration (something of value) exchanged by all parties.

4. **Governing Law**: Check which jurisdiction's laws govern the contract and where disputes would be handled.

5. **Termination Clauses**: Look for any provisions on how the contract can be ended and what happens then.

6. **Liability Limitations**: Review any caps on liability and exemptions from responsibility.

7. **Confidentiality**: Check if you're agreeing to keep certain information private.

8. **Dispute Resolution**: Look for clauses on arbitration, mediation, or litigation procedures.

This is general information and not legal advice. Please consult with a qualified legal professional for advice specific to your situation.""",
    "employment": """Employment contracts typically contain important provisions:

1. **Position and Duties**: Clearly defined job title and responsibilities.

2. **Compensation**: Salary, benefits, bonuses, and payment terms.

3. **Duration**: Whether it's permanent, fixed-term, or at-will employment.

4. **Termination**: Notice periods, severance, and grounds for termination.

5. **Confidentiality**: Restrictions on sharing company information.

6. **Non-Compete**: Restrictions on working for competitors after employment.

7. **Intellectual Property**: Who owns work created during employment.

This depends on your specific circumstances and jurisdiction. Consider consulting an employment lawyer.""",
    "default": """This is general legal information. The specific answer depends on your circumstances, jurisdiction, and the exact facts of your situation. I recommend consulting with a qualified legal professional who can review your specific case details and provide appropriate guidance. This is not legal advice."""
}

def get_mock_response(question: str) -> str:
    """
    Get a mock LLM response for testing purposes.
    
    Args:
        question: The legal question
        
    Returns:
        str: A mock response based on question keywords
    """
    question_lower = question.lower()
    
    if any(word in question_lower for word in ['contract', 'signing', 'agree']):
        return MOCK_RESPONSES["contract"]
    elif any(word in question_lower for word in ['employment', 'employee', 'job', 'hire']):
        return MOCK_RESPONSES["employment"]
    else:
        return MOCK_RESPONSES["default"]

def get_llm_response(question: str) -> str:
    """Get a cautious legal-information response from the configured Groq model."""
    if MOCK_LLM_ENABLED:
        logger.info("Using mock LLM response (mock mode enabled)")
        return get_mock_response(question)

    engineered_prompt = ANTI_HALLUCINATION_PROMPT + question
    logger.debug("Calling Groq model %s at %s", LLM_MODEL, LLM_BASE_URL)
    try:
        answer = groq_chat_completion(
            engineered_prompt,
            model=LLM_MODEL,
            temperature=0.3,
            timeout=LLM_TIMEOUT,
        )
    except GroqError as exc:
        logger.warning("Groq request failed: %s", exc)
        raise RuntimeError(
            f"Groq service failed after {LLM_MAX_RETRIES} attempt(s)"
        ) from exc
    logger.info("Groq response received (%s characters)", len(answer))
    return answer

__all__ = ['get_llm_response']
