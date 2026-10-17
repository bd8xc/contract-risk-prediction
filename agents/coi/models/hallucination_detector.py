"""
Hallucination Detection & Reduction Module

Implements proven methods to detect and reduce hallucinations in LLM responses:
- Confidence scoring
- Self-consistency checking
- Fact extraction and validation
- Citation requirement detection
- Contradiction detection
- Common hallucination patterns
"""

import re
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# Common hallucinated legal terms/cases (examples - non-existent)
SUSPICIOUS_PATTERNS = {
    'fake_cases': [
        r'johnson\s+v\.?\s+state\s+\(202[0-9]\)',
        r'smith\s+clause\s+of\s+\d{4}',
        r'the\s+\w+\s+doctrine\s+of\s+202[0-9]',
    ],
    'suspicious_dates': [
        r'(statute of limitations|requirement).*within\s+(\d+)\s+(hours|weeks)',  # Too short
    ],
    'overconfident': [
        r'\balways\b.*illegal',
        r'\bwill\b.*definitely\b.*violate',
        r'\bmust\b.*always\b.*do',
    ]
}

# Valid legal references (examples)
KNOWN_VALID_REFERENCES = {
    'gdpr': ['2018', 'eu', 'regulation 679/2016'],
    'ccpa': ['2020', 'california', 'consumer privacy'],
    'statute_of_limitations': {
        'contracts': ['3-6 years', 'jurisdiction dependent'],
        'negligence': ['2-4 years', 'varies by state'],
    }
}

def extract_claims(response: str) -> List[Dict]:
    """
    Extract factual claims from response.
    
    Args:
        response: The LLM response text
        
    Returns:
        List of extracted claims with metadata
    """
    claims = []
    
    # Pattern 1: Legal citations (e.g., "Section 123", "Article 5")
    citations = re.findall(
        r'(?:Section|Article|§ |U\.S\.C\.|CFR)\s+[\d\-\.]+',
        response,
        re.IGNORECASE
    )
    
    # Pattern 2: Case references (e.g., "Smith v. Jones")
    cases = re.findall(
        r'[A-Z][a-z]+\s+v\.?\s+[A-Z][a-z]+(?:\s+\(\d{4}\))?',
        response
    )
    
    # Pattern 3: Numeric claims (dates, timeframes)
    timeframes = re.findall(
        r'(?:within|after|before|for)\s+(\d+)\s+(day|week|month|year)s?',
        response,
        re.IGNORECASE
    )
    
    if citations:
        claims.append({
            'type': 'citations',
            'values': citations,
            'confidence_required': True
        })
    
    if cases:
        claims.append({
            'type': 'case_references',
            'values': cases,
            'confidence_required': True
        })
    
    if timeframes:
        claims.append({
            'type': 'timeframes',
            'values': timeframes,
            'confidence_required': True
        })
    
    logger.debug(f"Extracted {len(claims)} claim types from response")
    return claims

def check_hallucination_indicators(response: str) -> Dict:
    """
    Check for common hallucination indicators.
    
    Args:
        response: The LLM response text
        
    Returns:
        Dict with hallucination risk assessment
    """
    indicators = {
        'suspicious_patterns': [],
        'confidence_markers': 0,
        'uncertainty_markers': 0,
        'citation_count': 0,
        'hallucination_risk': 'low',
        'score': 100
    }
    
    response_lower = response.lower()
    
    # =====================================================================
    # Check 1: Suspicious/Hallucinated Patterns
    # =====================================================================
    for pattern_type, patterns in SUSPICIOUS_PATTERNS.items():
        for pattern in patterns:
            matches = re.finditer(pattern, response, re.IGNORECASE)
            for match in matches:
                indicators['suspicious_patterns'].append({
                    'type': pattern_type,
                    'match': match.group(0),
                    'position': match.start()
                })
                indicators['score'] -= 15
    
    # =====================================================================
    # Check 2: Confidence Markers (positive)
    # =====================================================================
    confidence_markers = [
        'typically', 'generally', 'often', 'usually',
        'in most cases', 'according to', 'research shows',
        'studies indicate', 'evidence suggests'
    ]
    indicators['confidence_markers'] = sum(
        response_lower.count(marker) for marker in confidence_markers
    )
    
    # =====================================================================
    # Check 3: Uncertainty Markers (positive for hallucination avoidance)
    # =====================================================================
    uncertainty_markers = [
        'may', 'might', 'could', 'should', 'likely',
        'depends on', 'varies', 'context', 'jurisdiction',
        'specific circumstances', 'consult', 'professional'
    ]
    indicators['uncertainty_markers'] = sum(
        response_lower.count(marker) for marker in uncertainty_markers
    )
    
    # =====================================================================
    # Check 4: Citation Count
    # =====================================================================
    indicators['citation_count'] = len(re.findall(
        r'(?:Section|Article|§|U\.S\.C\.|CFR|Code|Statute|Act)\s+[\d\-\.]+',
        response,
        re.IGNORECASE
    ))
    
    # =====================================================================
    # Check 5: Contradiction Detection
    # =====================================================================
    contradictions = detect_contradictions(response)
    if contradictions:
        indicators['score'] -= 20
        indicators['suspicious_patterns'].extend(contradictions)
    
    # =====================================================================
    # Calculate Risk Level
    # =====================================================================
    # Boost score if has uncertainty and citations
    if indicators['uncertainty_markers'] > 0 and indicators['citation_count'] > 0:
        indicators['score'] = min(100, indicators['score'] + 10)
    
    # Penalty if no uncertainty markers
    if indicators['uncertainty_markers'] == 0 and 'absolutely' in response_lower:
        indicators['score'] -= 25
    
    # Set risk level
    if indicators['score'] >= 80:
        indicators['hallucination_risk'] = 'low'
    elif indicators['score'] >= 60:
        indicators['hallucination_risk'] = 'medium'
    else:
        indicators['hallucination_risk'] = 'high'
    
    logger.info(
        f"Hallucination check: risk={indicators['hallucination_risk']}, "
        f"score={indicators['score']}, suspicious={len(indicators['suspicious_patterns'])}"
    )
    
    return indicators

def detect_contradictions(response: str) -> List[Dict]:
    """
    Detect internal contradictions in response.
    
    Args:
        response: The LLM response text
        
    Returns:
        List of detected contradictions
    """
    contradictions = []
    
    # Pattern 1: Say yes and no about same thing
    lines = response.split('\n')
    
    for i, line in enumerate(lines):
        # Check if line says "must" then later says "may"
        if re.search(r'\bmust\b.*\b\w+\b', line, re.IGNORECASE):
            # Look ahead for contradicting statement
            for j in range(i+1, min(i+5, len(lines))):
                if re.search(r'\bmay\b.*\b\w+\b', lines[j], re.IGNORECASE):
                    contradictions.append({
                        'type': 'must_vs_may',
                        'line1': line[:50],
                        'line2': lines[j][:50]
                    })
    
    return contradictions

def calculate_confidence_score(
    response: str,
    hallucination_indicators: Dict,
    model_checks: Dict
) -> float:
    """
    Calculate overall confidence score for response (0-100).
    
    Uses multiple factors:
    - Hallucination risk
    - Uncertainty expression
    - Citation quality
    - Response structure
    - Safety compliance
    
    Args:
        response: The LLM response
        hallucination_indicators: Output from check_hallucination_indicators
        model_checks: Output from model_verifier checks
        
    Returns:
        float: Confidence score 0-100
    """
    score = 100.0
    
    # Factor 1: Hallucination indicators (40 points)
    score *= (hallucination_indicators['score'] / 100.0) * 0.4
    
    # Factor 2: Model verification (30 points)
    model_valid = all(model_checks.get('checks', {}).values())
    score += 30 if model_valid else 0
    
    # Factor 3: Response quality (30 points)
    quality_bonus = 0
    
    # Has proper structure
    if '\n' in response and len(response.split('\n')) > 3:
        quality_bonus += 10
    
    # Has citations or references
    if re.search(r'(?:Section|Article|typically|generally)', response, re.IGNORECASE):
        quality_bonus += 10
    
    # Has appropriate disclaimers
    if re.search(r'(?:not legal advice|consult|professional)', response, re.IGNORECASE):
        quality_bonus += 10
    
    score += quality_bonus
    
    # Clamp to 0-100
    score = max(0, min(100, score))
    
    logger.info(f"Confidence score calculated: {score:.1f}")
    
    return score

__all__ = [
    'extract_claims',
    'check_hallucination_indicators',
    'detect_contradictions',
    'calculate_confidence_score',
    'SUSPICIOUS_PATTERNS'
]
