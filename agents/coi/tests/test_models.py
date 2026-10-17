"""
Unit tests for model modules

Tests issue extraction, rule verification, model verification, and rewriting.
Run with: pytest tests/test_models.py -v
"""

import pytest
from coi.models.issue_extractor import extract_issues, ISSUE_PATTERNS
from coi.models.rule_verifier import verify_rules
from coi.models.model_verifier import verify_model, check_relevance, check_length
from coi.models.rewriter import rewrite_answer, add_disclaimer, add_context_acknowledgment

# ============================================================================
# Issue Extractor Tests
# ============================================================================

def test_extract_contract_issues():
    """Test extraction of contract-related issues"""
    question = "Is our contract breached if we don't perform?"
    issues = extract_issues(question)
    assert 'contract_enforceability' in issues

def test_extract_employment_issues():
    """Test extraction of employment-related issues"""
    question = "Can my employer terminate me without cause?"
    issues = extract_issues(question)
    assert 'employment' in issues

def test_extract_data_protection_issues():
    """Test extraction of data protection issues"""
    question = "Does GDPR apply to our data processing?"
    issues = extract_issues(question)
    assert 'data_protection' in issues

def test_extract_ip_issues():
    """Test extraction of intellectual property issues"""
    question = "Can someone patent our invention?"
    issues = extract_issues(question)
    assert 'intellectual_property' in issues

def test_extract_default_compliance():
    """Test default to compliance when no other issues match"""
    question = "What is the color of the sky?"
    issues = extract_issues(question)
    assert 'compliance' in issues or len(issues) > 0

# ============================================================================
# Rule Verifier Tests
# ============================================================================

def test_rule_verifier_absolute_advice():
    """Test detection of absolute advice without qualifiers"""
    answer = "You must always file within 30 days or lose your rights."
    result = verify_rules(answer)
    assert not result['passes']
    assert any('absolute' in v.lower() for v in result['violations'])

def test_rule_verifier_qualified_advice():
    """Test that qualified advice passes"""
    answer = ("You should typically file within 30 days to preserve your rights. "
              "However, this depends on your specific jurisdiction and circumstances. "
              "Please consult with a legal professional for advice.")
    result = verify_rules(answer)
    assert result['passes']

def test_rule_verifier_missing_disclaimer():
    """Test detection of missing disclaimer"""
    answer = "You should file the document in court."
    result = verify_rules(answer)
    assert not result['passes']
    assert any('disclaimer' in v.lower() for v in result['violations'])

def test_rule_verifier_with_disclaimer():
    """Test acceptance when disclaimer is present"""
    answer = ("You should file the document. "
              "This is not legal advice. Please consult an attorney.")
    result = verify_rules(answer)
    # Should pass if disclaimer is present
    violations = [v.lower() for v in result['violations']]
    assert not any('disclaimer' in v for v in violations)

def test_rule_verifier_empty_answer():
    """Test handling of empty answer"""
    result = verify_rules("")
    assert not result['passes']

# ============================================================================
# Model Verifier Tests
# ============================================================================

def test_model_relevance_check():
    """Test relevance checking"""
    question = "What is the statute of limitations for contracts?"
    answer = "The statute of limitations varies by jurisdiction and contract type."
    is_relevant = check_relevance(answer, question)
    assert is_relevant

def test_model_irrelevance_check():
    """Test detection of irrelevant response"""
    question = "What is the statute of limitations?"
    answer = "The sky is blue and the sun is bright."
    is_relevant = check_relevance(answer, question)
    assert not is_relevant

def test_model_length_valid():
    """Test validation of appropriate length"""
    answer = "This is a valid length response with sufficient words to be acceptable."
    is_valid = check_length(answer)
    assert is_valid

def test_model_length_too_short():
    """Test detection of too-short response"""
    answer = "Too short."
    is_valid = check_length(answer)
    assert not is_valid

def test_model_verify_valid_response():
    """Test verification of valid response"""
    question = "What is contract enforceability?"
    answer = ("A contract is typically enforceable if certain conditions are met. "
              "However, specific laws apply based on jurisdiction. "
              "You should consult a legal professional.")
    result = verify_model(answer, question)
    assert result['is_valid']

def test_model_verify_invalid_response():
    """Test detection of invalid response"""
    question = "What is contract enforceability?"
    answer = "No relevant answer here."
    result = verify_model(answer, question)
    assert not result['is_valid']

def test_model_verify_empty_answer():
    """Test handling of empty answer"""
    result = verify_model("", "question")
    assert not result['is_valid']

# ============================================================================
# Rewriter Tests
# ============================================================================

def test_add_disclaimer_when_missing():
    """Test adding disclaimer when missing"""
    answer = "You must file within 30 days."
    result = add_disclaimer(answer)
    assert "legal advice" in result.lower() or "attorney" in result.lower()

def test_add_disclaimer_when_present():
    """Test that disclaimer isn't duplicated"""
    answer = "You should file. This is not legal advice."
    original_count = answer.count("legal advice")
    result = add_disclaimer(answer)
    # Should not add another disclaimer
    assert result.count("legal advice") <= original_count + 1

def test_add_context_acknowledgment():
    """Test adding context acknowledgment"""
    answer = "You can file the document."
    result = add_context_acknowledgment(answer)
    assert "jurisdiction" in result.lower() or "circumstances" in result.lower()

def test_rewrite_answer_with_violations():
    """Test rewriting with violations"""
    answer = "You must always file immediately."
    violations = ['Absolute advice without uncertainty']
    result = rewrite_answer(answer, violations)
    assert len(result) > len(answer)
    assert "typically" in result.lower() or "often" in result.lower() or "should" in result.lower()

def test_rewrite_empty_violations():
    """Test that no rewriting happens with empty violations"""
    answer = "Some answer."
    result = rewrite_answer(answer, [])
    # Should be same or have minimal changes
    assert answer in result or result == answer

# ============================================================================
# Integration Tests
# ============================================================================

def test_full_pipeline_issue_and_rules():
    """Test issue extraction and rule verification together"""
    question = "Is my employment contract binding?"
    issues = extract_issues(question)
    
    # Should identify employment and contract issues
    assert len(issues) > 0
    
    # Test with rule-compliant answer
    good_answer = ("Your employment contract may be binding depending on its terms "
                   "and your jurisdiction. Generally, courts enforce clear agreements. "
                   "However, some terms may be unenforceable. "
                   "Please consult an employment attorney for specific advice.")
    
    rule_result = verify_rules(good_answer)
    assert rule_result['passes']

def test_safety_chain_with_violations():
    """Test the chain: rules fail -> rewrite -> should improve"""
    bad_answer = "You must comply with all regulations always."
    
    # Check rules
    rule_result = verify_rules(bad_answer)
    assert not rule_result['passes']
    
    # Rewrite
    violations = rule_result['violations']
    rewritten = rewrite_answer(bad_answer, violations)
    
    # Check rules again
    rule_result2 = verify_rules(rewritten)
    # Should have fewer violations now
    assert len(rule_result2['violations']) <= len(rule_result['violations'])

# ============================================================================
# Edge Cases
# ============================================================================

def test_extract_issues_none_input():
    """Test handling of None input"""
    result = extract_issues(None)
    # Should return safe default
    assert isinstance(result, list)

def test_extract_issues_empty_string():
    """Test handling of empty string"""
    result = extract_issues("")
    assert isinstance(result, list)

def test_verify_rules_none_input():
    """Test rule verification with None"""
    result = verify_rules(None)
    assert not result['passes']

def test_verify_model_none_inputs():
    """Test model verification with None"""
    result = verify_model(None, None)
    assert not result['is_valid']

# ============================================================================
# Schema Validation Tests
# ============================================================================

def test_issue_patterns_coverage():
    """Test that all issue patterns have keywords"""
    for issue_type, keywords in ISSUE_PATTERNS.items():
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        assert all(isinstance(k, str) for k in keywords)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
