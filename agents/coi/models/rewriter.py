"""
Answer rewriting module

Automatically fixes safety violations in responses by adding qualifiers,
disclaimers, and context acknowledgments.
"""

import re
import logging
from ..config import ENABLE_AUTO_REWRITING

logger = logging.getLogger(__name__)

# Mappings for replacing absolute statements
ABSOLUTE_REPLACEMENTS = {
    r'\bmust\b': 'typically should',
    r'\bwill\b(?! be)': 'may',
    r'\balways\b': 'often',
    r'\bnever\b': 'rarely',
    r'\bdefinitely\b': 'likely',
    r'\bcertainly\b': 'likely',
    r'\bguarantee\b': 'may help',
    r'\bconfirm\b': 'suggest',
}

# Standard disclaimer to add if missing
STANDARD_DISCLAIMER = (
    "Disclaimer: This is general information and not legal advice. "
    "Please consult with a qualified legal professional for advice "
    "specific to your situation."
)

# Context acknowledgment statement
CONTEXT_ACKNOWLEDGMENT = (
    "Please note that the applicability of this information depends on "
    "your particular circumstances, jurisdiction, and specific facts. "
    "Legal requirements vary significantly by location."
)

def fix_absolute_statements(answer: str) -> str:
    """
    Replace absolute statements with qualified language.
    
    Args:
        answer: The original response text
        
    Returns:
        str: Response with softened absolute statements
    """
    try:
        fixed = answer
        
        for pattern, replacement in ABSOLUTE_REPLACEMENTS.items():
            fixed = re.sub(pattern, replacement, fixed, flags=re.IGNORECASE)
        
        logger.debug("Fixed absolute statements in answer")
        return fixed
        
    except Exception as e:
        logger.warning(f"Error fixing absolute statements: {str(e)}")
        return answer

def add_disclaimer(answer: str) -> str:
    """
    Add disclaimer if not already present.
    
    Args:
        answer: The response text
        
    Returns:
        str: Response with disclaimer added
    """
    try:
        # Check if disclaimer-like text already exists
        disclaimer_patterns = [
            r'not.*legal advice',
            r'consult.*attorney',
            r'professional.*advice',
        ]
        
        has_disclaimer = any(
            re.search(p, answer, re.IGNORECASE)
            for p in disclaimer_patterns
        )
        
        if not has_disclaimer:
            answer = answer + "\n\n" + STANDARD_DISCLAIMER
            logger.debug("Added disclaimer to answer")
        
        return answer
        
    except Exception as e:
        logger.warning(f"Error adding disclaimer: {str(e)}")
        return answer

def add_context_acknowledgment(answer: str) -> str:
    """
    Add context acknowledgment if not already present.
    
    Args:
        answer: The response text
        
    Returns:
        str: Response with context acknowledgment
    """
    try:
        # Check if context acknowledgment already exists
        context_keywords = ['jurisdiction', 'circumstances', 'specific', 'depends']
        
        has_acknowledgment = any(
            keyword in answer.lower() for keyword in context_keywords
        )
        
        if not has_acknowledgment:
            answer = answer + "\n\n" + CONTEXT_ACKNOWLEDGMENT
            logger.debug("Added context acknowledgment to answer")
        
        return answer
        
    except Exception as e:
        logger.warning(f"Error adding context acknowledgment: {str(e)}")
        return answer

def rewrite_answer(answer: str, violations: list) -> str:
    """
    Rewrite answer to fix safety violations.
    
    Args:
        answer: The original LLM response
        violations: List of safety violations to fix
        
    Returns:
        str: Rewritten response with safety fixes
    """
    try:
        if not ENABLE_AUTO_REWRITING:
            logger.debug("Auto-rewriting disabled, returning original answer")
            return answer
        
        if not answer or not isinstance(answer, str):
            logger.warning("Invalid answer for rewriting")
            return answer
        
        rewritten = answer
        
        # ====================================================================
        # Fix absolute advice violations
        # ====================================================================
        if any('absolute' in v.lower() for v in violations):
            rewritten = fix_absolute_statements(rewritten)
        
        # ====================================================================
        # Add disclaimer if missing
        # ====================================================================
        if any('disclaimer' in v.lower() for v in violations):
            rewritten = add_disclaimer(rewritten)
        
        # ====================================================================
        # Add context acknowledgment if missing
        # ====================================================================
        if any('context' in v.lower() for v in violations):
            rewritten = add_context_acknowledgment(rewritten)
        
        # Fallback: if violations exist but none matched, add both
        if violations and rewritten == answer:
            rewritten = add_disclaimer(rewritten)
            rewritten = add_context_acknowledgment(rewritten)
        
        logger.info(f"Answer rewritten to address {len(violations)} violations")
        return rewritten
        
    except Exception as e:
        logger.error(f"Error rewriting answer: {str(e)}")
        # Return original answer if rewriting fails
        return answer + "\n\n[SAFETY NOTE: Response returned as rewriting encountered an error]"

__all__ = [
    'rewrite_answer',
    'fix_absolute_statements',
    'add_disclaimer',
    'add_context_acknowledgment'
]
