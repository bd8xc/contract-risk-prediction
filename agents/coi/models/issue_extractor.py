"""
Issue extraction and categorization module

Categorizes legal questions into specific issue types for targeted verification.
"""

import logging

logger = logging.getLogger(__name__)

# Issue categories with keyword patterns
ISSUE_PATTERNS = {
    'contract_enforceability': [
        'contract', 'enforce', 'breach', 'valid', 'void', 'agreement',
        'binding', 'obligation', 'performance', 'terms'
    ],
    'termination': [
        'terminate', 'end', 'close', 'cancellation', 'dissolution',
        'rescind', 'cancel', 'exit', 'withdrawal'
    ],
    'liability': [
        'liable', 'responsible', 'damages', 'claim', 'sue', 'lawsuit',
        'negligence', 'indemnif', 'immunity', 'protected'
    ],
    'data_protection': [
        'gdpr', 'privacy', 'data', 'ccpa', 'protection', 'personal data',
        'consent', 'processing', 'dpa', 'confidential'
    ],
    'employment': [
        'employment', 'employee', 'employer', 'labor', 'wage', 'termination',
        'contract', 'worker', 'compensation', 'discrimination', 'harassment'
    ],
    'intellectual_property': [
        'copyright', 'patent', 'trademark', 'ip', 'infringement',
        'intellectual property', 'license', 'royalty', 'proprietary'
    ],
    'compliance': [
        'compliance', 'regulation', 'law', 'requirement', 'legal',
        'statute', 'regulatory', 'obligation', 'standard'
    ]
}

def extract_issues(question: str) -> list:
    """
    Extract issue categories from a legal question.
    
    Args:
        question: The legal question to analyze
        
    Returns:
        list: List of matched issue categories (can be multiple)
    """
    try:
        if not question or not isinstance(question, str):
            logger.warning("Invalid question for issue extraction")
            return []
        
        issues = []
        question_lower = question.lower()
        
        # Check each issue category
        for issue_type, keywords in ISSUE_PATTERNS.items():
            if any(keyword in question_lower for keyword in keywords):
                issues.append(issue_type)
        
        # Default to compliance if no issues found
        if not issues:
            issues.append('compliance')
        
        logger.debug(f"Extracted issues from question: {issues}")
        return issues
        
    except Exception as e:
        logger.error(f"Error extracting issues: {str(e)}")
        return ['compliance']  # Safe default

__all__ = ['extract_issues', 'ISSUE_PATTERNS']
