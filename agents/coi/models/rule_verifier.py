"""
Rule-based verification module

Enforces hard safety rules on LLM responses to ensure appropriate language
and required disclaimers.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Patterns for absolute advice that should be qualified
ABSOLUTE_PATTERNS = [
    r'\bmust\b',
    r'\bwill\b(?! be able)',
    r'\balways\b',
    r'\bnever\b',
    r'\bdefinitely\b',
    r'\bcertainly\b',
    r'\bguarantee\b',
    r'\bconfirm\b(?!ing)',
]

# Uncertainty markers that qualify statements
UNCERTAINTY_MARKERS = [
    'typically', 'often', 'generally', 'may', 'might',
    'should', 'could', 'consider', 'suggest', 'appears',
    'likely', 'possible', 'probable', 'usually', 'can'
]

# Disclaimer patterns to look for
DISCLAIMER_PATTERNS = [
    r'not.*legal advice',
    r'consult.*(?:attorney|lawyer|professional)',
    r'(?:qualified|professional).*(?:legal|lawyer|attorney)',
    r'for (?:legal|professional) advice',
]

# Context acknowledgment keywords
CONTEXT_KEYWORDS = [
    'depends', 'context', 'specific', 'circumstances',
    'jurisdiction', 'situation', 'particular'
]

def verify_rules(answer: str) -> dict:
    """
    Verify that response follows hard safety rules.
    
    Args:
        answer: The LLM response to verify
        
    Returns:
        dict: Verification result with passes flag and violations list
    """
    try:
        if not answer or not isinstance(answer, str):
            logger.warning("Invalid answer for rule verification")
            return {
                'passes': False,
                'violations': ['Empty or invalid response']
            }
        
        violations = []
        answer_lower = answer.lower()
        
        # ====================================================================
        # Rule 1: Check for absolute advice without uncertainty qualifiers
        # ====================================================================
        absolute_count = sum(
            len(re.findall(pattern, answer, re.IGNORECASE))
            for pattern in ABSOLUTE_PATTERNS
        )
        
        uncertainty_count = sum(
            answer_lower.count(marker) for marker in UNCERTAINTY_MARKERS
        )
        
        if absolute_count > 0 and uncertainty_count == 0:
            violations.append('Absolute advice without uncertainty qualifiers')
            logger.debug(f"Found {absolute_count} absolute patterns, no uncertainty markers")
        
        # ====================================================================
        # Rule 2: Check for required disclaimer
        # ====================================================================
        has_disclaimer = any(
            re.search(pattern, answer, re.IGNORECASE)
            for pattern in DISCLAIMER_PATTERNS
        )
        
        if not has_disclaimer:
            violations.append('Missing disclaimer about legal advice')
            logger.debug("No disclaimer found in response")
        
        # ====================================================================
        # Rule 3: Check for context acknowledgment
        # ====================================================================
        has_context = any(
            keyword in answer_lower for keyword in CONTEXT_KEYWORDS
        )
        
        if not has_context:
            violations.append('No acknowledgment of context/jurisdiction dependency')
            logger.debug("No context acknowledgment found")
        
        # ====================================================================
        # Rule 4: Check response length
        # ====================================================================
        words = len(answer.split())
        if words < 10:
            violations.append('Response too brief')
            logger.debug(f"Response too brief: {words} words")
        
        # ====================================================================
        # Determine pass/fail
        # ====================================================================
        passes = len(violations) == 0
        
        logger.info(f"Rule verification result: passes={passes}, violations={violations}")
        
        return {
            'passes': passes,
            'violations': violations,
            'checks': {
                'absolute_statements': absolute_count,
                'uncertainty_markers': uncertainty_count,
                'has_disclaimer': has_disclaimer,
                'has_context_acknowledgment': has_context,
                'response_words': words
            }
        }
        
    except Exception as e:
        logger.error(f"Error in rule verification: {str(e)}")
        return {
            'passes': False,
            'violations': [f'Verification error: {str(e)}']
        }

__all__ = ['verify_rules', 'ABSOLUTE_PATTERNS', 'UNCERTAINTY_MARKERS']
