"""
Advanced Fact Validation Module

Validates responses against known legal facts, improves hallucination detection,
and adds semantic similarity checking.
"""

import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# =====================================================================
# VERIFIED LEGAL FACTS DATABASE
# =====================================================================
# Only facts we're confident are correct (general principles)
VERIFIED_LEGAL_FACTS = {
    "contract": {
        "requirements": [
            "offer",
            "acceptance", 
            "consideration",
            "mutual intent",
            "capacity",
            "legality"
        ],
        "principles": [
            "contracts require agreement between parties",
            "consideration typically involves exchange of value",
            "contracts can be written or oral",
            "breach may result in damages",
            "contracts are enforced by law",
            "parties must have authority",
            "terms must be clearly stated",
            "governing law determines interpretation",
            "intellectual property rights",
            "termination provisions",
            "dispute resolution",
            "confidentiality",
        ],
        # Simpler keywords to detect principle references
        "keywords": [
            "offer",
            "acceptance",
            "consideration",
            "parties",
            "authority",
            "terms",
            "conditions",
            "governing law",
            "jurisdiction",
            "breach",
            "damages",
            "remedy",
            "remedy",
            "confidentiality",
            "termination",
            "dispute",
            "intellectual property",
        ]
    },
    "employment": {
        "principles": [
            "employment laws vary by jurisdiction",
            "employment discrimination is illegal in most jurisdictions",
            "wages must be paid according to law",
            "safety standards typically apply to workplaces",
            "termination notice requirements vary",
        ]
    },
    "data_protection": {
        "facts": [
            "GDPR applies to EU personal data",
            "CCPA applies to California residents",
            "data minimization is a principle",
            "consent is typically required",
            "data breaches must be reported in many jurisdictions",
        ]
    },
    "intellectual_property": {
        "facts": [
            "copyright protection is automatic",
            "attribution does not grant permission",
            "patents require registration",
            "trademark protection requires use",
            "fair use exists in some jurisdictions",
        ]
    }
}

# =====================================================================
# KNOWN FALSE PATTERNS (Common Hallucinations)
# =====================================================================
KNOWN_HALLUCINATIONS = {
    # Fake case names
    "fake_cases": [
        r"(?:smith|johnson|anderson|williams)\s+v\.?\s+(?:corp|universal|system|digital)",
        r"(?:the\s+)?\w+\s+doctrine\s+of\s+20\d{2}",
        r"(?:clause|act|law)\s+(?:\d+\.)?\d+\s+of\s+20\d{2}",
    ],
    # Fake statute numbers (too specific, wrong format)
    "fake_statutes": [
        r"section\s+\d{3,}\.\d+\.\d+\s+of\s+the\s+\w+\s+(?:act|code)\s+\(20\d{2}\)",
        r"cfr\s+\d{4}\.\d{1,2}\.\d{1,3}\.\d+",  # CFR doesn't go that deep
    ],
    # Impossible timeframes
    "impossible_timeframes": [
        r"within\s+(?:1|2|3)\s+hours?\s+(?:to|of|for)\s+(?:sign|notify|comply)",
        r"statute\s+of\s+limitations?\s+(?:of|is)\s+(?:1|2)\s+hours?",
    ]
}

# =====================================================================
# SEMANTIC INCONSISTENCY PATTERNS
# =====================================================================
SEMANTIC_INCONSISTENCIES = {
    "contradictory_pairs": [
        ("always required", "never required"),
        ("must do", "must not do"),
        ("guaranteed", "no guarantee"),
        ("automatically", "requires approval"),
        ("legally binding", "not enforceable"),
    ],
    "suspicious_absolutes_in_legal": [
        "always illegal",
        "guaranteed to win",
        "will definitely",
        "absolutely protected",
        "impossible to",
    ]
}

def validate_against_known_facts(response: str, issue_type: str) -> Dict:
    """
    Validate response against known legal facts for the issue type.
    
    Args:
        response: The LLM response
        issue_type: The legal issue category
        
    Returns:
        Dict with validation results
    """
    validation = {
        'is_consistent': True,
        'inconsistencies': [],
        'references_verified_facts': False,
        'confidence_adjustment': 0,
        'recommendations': []
    }
    
    if issue_type not in VERIFIED_LEGAL_FACTS:
        logger.debug(f"No verified facts for issue type: {issue_type}")
        return validation
    
    facts = VERIFIED_LEGAL_FACTS[issue_type]
    response_lower = response.lower()
    
    # =====================================================================
    # Check 1: Does response reference known keywords/principles?
    # =====================================================================
    keyword_count = 0
    for keyword in facts.get("keywords", []):
        if keyword.lower() in response_lower:
            keyword_count += 1
    
    # If response mentions multiple keywords from verified facts, it's good
    if keyword_count >= 3:
        validation['references_verified_facts'] = True
        validation['confidence_adjustment'] += 10
        logger.debug(f"Found {keyword_count} verified fact keywords")
    
    # =====================================================================
    # Check 2: Full principle matching
    # =====================================================================
    for principle in facts.get("principles", []):
        if principle.lower() in response_lower:
            validation['references_verified_facts'] = True
            validation['confidence_adjustment'] += 5
    
    return validation

def detect_known_hallucinations(response: str) -> Dict:
    """
    Detect known hallucination patterns.
    
    Args:
        response: The LLM response
        
    Returns:
        Dict with hallucination detection results
    """
    detections = {
        'detected_hallucinations': [],
        'confidence_penalty': 0,
        'severity': 'none'
    }
    
    for halluc_type, patterns in KNOWN_HALLUCINATIONS.items():
        for pattern in patterns:
            matches = re.finditer(pattern, response, re.IGNORECASE)
            for match in matches:
                detections['detected_hallucinations'].append({
                    'type': halluc_type,
                    'text': match.group(0),
                    'position': match.start()
                })
                detections['confidence_penalty'] += 25
    
    if detections['detected_hallucinations']:
        if len(detections['detected_hallucinations']) > 3:
            detections['severity'] = 'critical'
        elif len(detections['detected_hallucinations']) > 1:
            detections['severity'] = 'high'
        else:
            detections['severity'] = 'medium'
    
    logger.info(
        f"Detected {len(detections['detected_hallucinations'])} hallucinations: "
        f"severity={detections['severity']}"
    )
    
    return detections

def detect_logical_inconsistencies(response: str) -> List[Dict]:
    """
    Detect logical inconsistencies and contradictions.
    
    Args:
        response: The LLM response
        
    Returns:
        List of detected inconsistencies
    """
    inconsistencies = []
    response_lower = response.lower()
    sentences = re.split(r'[.!?]\s+', response_lower)
    
    # =====================================================================
    # Check 1: Contradictory pairs in same response
    # =====================================================================
    for positive, negative in SEMANTIC_INCONSISTENCIES["contradictory_pairs"]:
        has_positive = any(positive in sent for sent in sentences)
        has_negative = any(negative in sent for sent in sentences)
        
        if has_positive and has_negative:
            inconsistencies.append({
                'type': 'logical_contradiction',
                'positive_claim': positive,
                'negative_claim': negative,
                'severity': 'high'
            })
    
    # =====================================================================
    # Check 2: Suspicious absolutes
    # =====================================================================
    for absolute in SEMANTIC_INCONSISTENCIES["suspicious_absolutes_in_legal"]:
        if absolute in response_lower:
            # Check if followed by legal qualifier
            pattern = re.escape(absolute) + r'(?:\s+in\s+\w+|\s+subject\s+to|\s+typically)?'
            matches = re.finditer(pattern, response_lower)
            
            for match in matches:
                match_text = match.group(0)
                has_qualifier = any(q in match_text for q in ['subject to', 'typically', 'may', 'might'])
                
                if not has_qualifier:
                    inconsistencies.append({
                        'type': 'unqualified_absolute',
                        'text': absolute,
                        'severity': 'medium'
                    })
    
    logger.info(f"Detected {len(inconsistencies)} logical inconsistencies")
    return inconsistencies

def calculate_robustness_score(
    response: str,
    issue_type: str,
    base_confidence: float
) -> Tuple[float, List[str]]:
    """
    Calculate comprehensive robustness score with detailed reasoning.
    
    Args:
        response: The LLM response
        issue_type: The legal issue category
        base_confidence: Base confidence from model verifier
        
    Returns:
        Tuple of (adjusted_confidence, recommendations)
    """
    confidence = base_confidence
    recommendations = []
    
    # =====================================================================
    # Apply adjustments
    # =====================================================================
    
    # Check against verified facts
    fact_validation = validate_against_known_facts(response, issue_type)
    confidence += fact_validation['confidence_adjustment']
    
    if not fact_validation['references_verified_facts']:
        recommendations.append(
            "Response does not reference verified legal principles - may need lawyer review"
        )
    
    # Check for known hallucinations
    halluc_check = detect_known_hallucinations(response)
    confidence -= halluc_check['confidence_penalty']
    
    if halluc_check['detected_hallucinations']:
        recommendations.append(
            f"ALERT: {len(halluc_check['detected_hallucinations'])} suspected hallucinations detected"
        )
    
    # Check for logical inconsistencies
    inconsistencies = detect_logical_inconsistencies(response)
    confidence -= len(inconsistencies) * 10
    
    if inconsistencies:
        high_severity = [i for i in inconsistencies if i.get('severity') == 'high']
        if high_severity:
            recommendations.append(
                f"ALERT: {len(high_severity)} logical contradictions found - REQUIRES REVIEW"
            )
    
    # =====================================================================
    # Clamp confidence and add recommendations
    # =====================================================================
    confidence = max(0, min(100, confidence))
    
    if confidence < 40:
        recommendations.append("REJECT: Confidence too low, do not use without lawyer review")
    elif confidence < 60:
        recommendations.append("CAUTION: Low confidence - recommend lawyer review before use")
    elif confidence < 80:
        recommendations.append("REVIEW: Standard confidence - lawyer review recommended")
    else:
        recommendations.append("OK: Confidence acceptable - still recommend disclosure to user")
    
    logger.info(
        f"Robustness score: {confidence:.1f}/100, "
        f"issues: {len(recommendations)}"
    )
    
    return confidence, recommendations

__all__ = [
    'validate_against_known_facts',
    'detect_known_hallucinations',
    'detect_logical_inconsistencies',
    'calculate_robustness_score',
    'VERIFIED_LEGAL_FACTS',
    'KNOWN_HALLUCINATIONS'
]
