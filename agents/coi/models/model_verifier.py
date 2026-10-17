"""
Model-based verification module

Detects hallucinations, irrelevant responses, and validates response quality
from the LLM. Uses confidence scoring and advanced hallucination detection.
Integrated with fact validation for improved robustness.
"""

import re
import json
import logging
from .hallucination_detector import (
    check_hallucination_indicators,
    extract_claims,
    calculate_confidence_score
)
from .fact_validator import (
    detect_known_hallucinations,
    detect_logical_inconsistencies,
    validate_against_known_facts,
    calculate_robustness_score
)

logger = logging.getLogger(__name__)

def check_relevance(answer: str, question: str) -> bool:
    """
    Check if response is relevant to the question.
    
    Args:
        answer: The LLM response
        question: The original question
        
    Returns:
        bool: True if response appears relevant
    """
    try:
        # Extract key terms (words longer than 3 chars)
        question_terms = set(
            word.lower() for word in question.split()
            if len(word) > 3 and not word.startswith('the')
        )
        
        # Check overlap
        if not question_terms:
            return True
        
        answer_terms = set(
            word.lower() for word in answer.split()
            if len(word) > 3
        )
        
        overlap = len(question_terms & answer_terms) / len(question_terms)
        is_relevant = overlap > 0.2  # At least 20% overlap
        
        logger.debug(f"Relevance check: {overlap:.2%} overlap (threshold: 20%)")
        return is_relevant
        
    except Exception as e:
        logger.warning(f"Error in relevance check: {str(e)}")
        return True  # Assume relevant on error

def check_length(answer: str) -> bool:
    """
    Check if response length is reasonable.
    
    Args:
        answer: The LLM response
        
    Returns:
        bool: True if length is acceptable
    """
    try:
        words = len(answer.split())
        min_words = 10
        max_words = 5000
        
        is_valid = min_words <= words <= max_words
        logger.debug(f"Length check: {words} words (range: {min_words}-{max_words})")
        
        return is_valid
        
    except Exception as e:
        logger.warning(f"Error in length check: {str(e)}")
        return True

def check_json_validity(answer: str) -> bool:
    """
    Check if any JSON in response is valid.
    
    Args:
        answer: The LLM response
        
    Returns:
        bool: True if no JSON or JSON is valid
    """
    try:
        # Look for JSON objects
        json_matches = re.findall(r'\{[^{}]*\}', answer, re.DOTALL)
        
        if not json_matches:
            return True  # No JSON to validate
        
        # Try to parse each JSON match
        for json_str in json_matches:
            try:
                json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON found in response: {json_str[:100]}")
                return False
        
        return True
        
    except Exception as e:
        logger.warning(f"Error in JSON validity check: {str(e)}")
        return True

def verify_model(answer: str, question: str) -> dict:
    """
    Verify response quality and detect hallucinations using advanced detection.
    
    Args:
        answer: The LLM response to verify
        question: The original question
        
    Returns:
        dict: Comprehensive verification with confidence score and hallucination analysis
    """
    try:
        if not answer or not isinstance(answer, str):
            logger.warning("Invalid answer for model verification")
            return {
                'is_valid': False,
                'reason': 'Empty or invalid response',
                'checks': {},
                'confidence_score': 0,
                'hallucination_risk': 'high',
                'claimed_facts': []
            }
        
        # =====================================================================
        # Run basic checks
        # =====================================================================
        checks = {
            'relevant': check_relevance(answer, question),
            'length': check_length(answer),
            'json_valid': check_json_validity(answer)
        }
        
        # =====================================================================
        # Advanced Hallucination Detection
        # =====================================================================
        hallucination_indicators = check_hallucination_indicators(answer)
        
        # =====================================================================
        # Extract Issue Type for Fact Validation
        # =====================================================================
        # Try to infer issue type from question
        issue_type = 'compliance'  # default
        if any(w in question.lower() for w in ['liability', 'liable', 'damages', 'injured']):
            issue_type = 'liability'
        elif any(w in question.lower() for w in ['gdpr', 'data', 'privacy', 'ccpa']):
            issue_type = 'data_protection'
        elif any(w in question.lower() for w in ['copyright', 'patent', 'trademark', 'intellectual']):
            issue_type = 'intellectual_property'
        elif any(w in question.lower() for w in ['contract', 'agreement', 'binding']):
            issue_type = 'contract'
        elif any(w in question.lower() for w in ['employment', 'employee', 'labor', 'wage']):
            issue_type = 'employment'
        
        # =====================================================================
        # Enhanced Fact Validation
        # =====================================================================
        known_hallucinations = detect_known_hallucinations(answer)
        logical_inconsistencies = detect_logical_inconsistencies(answer)
        fact_validation = validate_against_known_facts(answer, issue_type)
        
        # =====================================================================
        # Extract Claims for Review
        # =====================================================================
        claimed_facts = extract_claims(answer)
        
        # =====================================================================
        # Calculate Confidence Score
        # =====================================================================
        base_confidence = calculate_confidence_score(
            answer, 
            hallucination_indicators,
            {'checks': checks}
        )
        
        # Calculate robust confidence with fact validation
        robust_confidence, recommendations = calculate_robustness_score(
            answer,
            issue_type,
            base_confidence
        )
        
        # =====================================================================
        # Determine overall validity
        # =====================================================================
        basic_valid = all(checks.values())
        
        # High hallucination risk or low confidence = invalid for production
        high_risk = hallucination_indicators['hallucination_risk'] == 'high'
        critical_hallucinations = known_hallucinations.get('severity') == 'critical'
        has_logical_contradictions = len(logical_inconsistencies) > 0
        low_confidence = robust_confidence < 50
        
        is_valid = (basic_valid and not high_risk and not critical_hallucinations 
                   and not has_logical_contradictions and not low_confidence)
        
        # =====================================================================
        # Generate detailed reason
        # =====================================================================
        reasons = []
        
        if not basic_valid:
            failed = [k for k, v in checks.items() if not v]
            reasons.append(f"Failed basic checks: {', '.join(failed)}")
        
        if critical_hallucinations:
            suspicious = len(known_hallucinations['detected_hallucinations'])
            reasons.append(f"CRITICAL: {suspicious} likely hallucinations detected")
        elif high_risk:
            suspicious = len(hallucination_indicators['suspicious_patterns'])
            reasons.append(f"High hallucination risk ({suspicious} patterns)")
        
        if has_logical_contradictions:
            reasons.append(f"Logical contradictions detected ({len(logical_inconsistencies)})")
        
        if low_confidence:
            reasons.append(f"Low robustness score: {robust_confidence:.1f}/100")
        
        if not reasons:
            reasons.append("Valid response - meets robustness standards")
        
        reason = "; ".join(reasons)
        
        logger.info(
            f"Model verification: valid={is_valid}, "
            f"robust_confidence={robust_confidence:.1f}, "
            f"hallucinations={len(known_hallucinations['detected_hallucinations'])}, "
            f"contradictions={len(logical_inconsistencies)}"
        )
        
        return {
            'is_valid': is_valid,
            'reason': reason,
            'checks': checks,
            'confidence_score': robust_confidence,
            'hallucination_risk': hallucination_indicators['hallucination_risk'],
            'hallucination_indicators': hallucination_indicators,
            'claimed_facts': claimed_facts,
            'known_hallucinations': known_hallucinations,
            'logical_inconsistencies': logical_inconsistencies,
            'fact_validation': fact_validation,
            'recommendations': recommendations,
            'issue_type': issue_type
        }
        
    except Exception as e:
        logger.error(f"Error in model verification: {str(e)}")
        return {
            'is_valid': False,
            'reason': f'Verification error: {str(e)}',
            'checks': {}
        }

__all__ = ['verify_model', 'check_relevance', 'check_length', 'check_json_validity']
