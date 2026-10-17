import json
import os
import sys
from typing import Dict, List, Literal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, StrictBool, ValidationError

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from groq_client import GroqError, groq_chat_completion, groq_model_available


class _RelevantSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: str
    relevance: str


class _WeakSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: str
    reason: str


class _LegalAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessed_risk: Literal["Low", "Medium", "High"]
    agreement_with_model: StrictBool
    summary: str
    risk_reasoning: str
    relevant_sections: list[_RelevantSection]
    irrelevant_or_weak_sections: list[_WeakSection]
    contractual_concern: str
    suggested_mitigation: str
    human_review_required: StrictBool
    evidence_sufficient: StrictBool


def _unknown_analysis(reason: str) -> dict:
    return {
        "assessed_risk": "Unknown",
        "agreement_with_model": False,
        "summary": reason,
        "risk_reasoning": "No validated explanation is available.",
        "relevant_sections": [],
        "irrelevant_or_weak_sections": [],
        "contractual_concern": "Manual review required.",
        "suggested_mitigation": "Review the clause and legal sources manually.",
        "human_review_required": True,
        "evidence_sufficient": False,
    }


class GroqLegalLLM:
    """Groq-backed legal reasoning for the contract-risk agent.

    The LLM does NOT replace LegalBERT and does NOT independently
    retrieve law.

    It receives:

        1. Original contract clause
        2. LegalBERT risk prediction
        3. Retrieved Indian statutory provisions

    It then produces a grounded explanation.

    Groq receives the prompt through its hosted API.
    """

    def __init__(self, model_name=None):
        self.model_name = model_name or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    ##########################################################
    # CHECK CONNECTION
    ##########################################################

    def check_connection(self):

        return groq_model_available(self.model_name)

    ##########################################################
    # FORMAT LEGALBERT RESULT
    ##########################################################

    @staticmethod
    def _format_model_result(
        model_result: Dict,
    ) -> str:

        prediction = (
            model_result.get(
                "prediction",
                "Unknown",
            )
        )

        model_score = float(
            model_result.get(
                "model_score",
                0.0,
            )
        )

        class_scores = (
            model_result.get(
                "class_scores",
                {}
            )
        )

        lines = [

            f"Predicted class: "
            f"{prediction}",

            f"Model score: "
            f"{model_score * 100:.2f}%",

            "Class scores:",
        ]

        for label, score in (
            class_scores.items()
        ):

            display_label = (
                "Baseline"
                if label == "Seed"
                else label
            )

            lines.append(
                f"- {display_label}: "
                f"{float(score) * 100:.2f}%"
            )

        return "\n".join(
            lines
        )

    ##########################################################
    # FORMAT RETRIEVED LAW
    ##########################################################

    @staticmethod
    def _format_legal_context(
        retrieved_law: List[Dict],
    ) -> str:

        if not retrieved_law:

            return (
                "No statutory provisions "
                "were retrieved."
            )

        blocks = []

        for item in retrieved_law:

            section = item.get(
                "section",
                "Unknown",
            )

            heading = item.get(
                "heading",
                "",
            )

            text = item.get(
                "text",
                "",
            )

            score = item.get(
                "score"
            )

            block = [

                (
                    f"SECTION {section}: "
                    f"{heading}"
                ),

            ]

            if score is not None:

                block.append(
                    "Retrieval similarity: "
                    f"{float(score):.4f}"
                )

            block.extend(
                [
                    "Provision:",
                    text,
                ]
            )

            blocks.append(
                "\n".join(
                    block
                )
            )

        return (
            "\n\n"
            "------------------------------"
            "\n\n"
        ).join(
            blocks
        )

    ##########################################################
    # BUILD PROMPT
    ##########################################################

    def _build_prompt(
        self,
        clause: str,
        model_result: Dict | None,
        retrieved_law: List[Dict],
    ) -> str:

        model_context = (
            self._format_model_result(model_result)
            if model_result is not None
            else "No LegalBERT classifier result is available. Assess the clause from the supplied evidence only; do not claim that a classifier produced a score or prediction."
        )

        legal_context = (
            self._format_legal_context(
                retrieved_law
            )
        )

        prompt = f"""
You are the reasoning component of an automated Indian commercial
contract risk analysis system.

You must analyze the supplied contract clause using ONLY the evidence
provided below.

You are given:

1. The original contract clause.
2. A LegalBERT risk signal when the trained classifier is available.
3. Candidate statutory provisions retrieved from the Indian Contract
   Act, 1872.

IMPORTANT RELEVANCE RULES:

- Retrieved statutory provisions are candidate evidence only.
- Do not select a provision merely because it contains words similar
  to the contract clause.
- Compare the actual legal relationship and factual context described
  by each provision with the supplied clause.
- Prefer a general provision that directly defines or governs the
  contractual concept over a specialized provision that applies only
  to a different legal relationship.
- If a provision concerns principal-agent relationships, agency,
  criminal conduct, guarantee, bailment, pledge, or another specialized
  relationship, do not treat it as directly relevant unless that same
  relationship exists in the supplied clause.
- Explicitly place retrieved but inapplicable provisions under
  irrelevant_or_weak_sections.
- Do not claim that a clause violates a statutory provision unless the
  supplied statutory text itself supports that conclusion.
- Distinguish contractual risk from statutory illegality.

============================================================
CONTRACT CLAUSE
============================================================

{clause}

============================================================
LEGALBERT RISK SIGNAL
============================================================

{model_context}

============================================================
RETRIEVED STATUTORY CONTEXT
============================================================

{legal_context}

============================================================
TASK
============================================================

Return ONLY valid JSON using exactly this structure:

{{
    "assessed_risk": "Low | Medium | High",
    "agreement_with_model": true,
    "summary": "Short overall assessment.",
    "risk_reasoning": "Explain the contractual risk based on the clause.",
    "relevant_sections": [
        {{
            "section": "section number",
            "relevance": "Why this retrieved section is relevant."
        }}
    ],
    "irrelevant_or_weak_sections": [
        {{
            "section": "section number",
            "reason": "Why this retrieved section should not be relied upon."
        }}
    ],
    "contractual_concern": "Main contractual concern.",
    "suggested_mitigation": "Possible drafting or review mitigation.",
    "human_review_required": true,
    "evidence_sufficient": true
}}

Do not include markdown.

Do not include text before or after the JSON.
"""

        return prompt.strip()

    ##########################################################
    # ANALYZE
    ##########################################################

    def analyze(
        self,
        clause: str,
        model_result: Dict | None,
        retrieved_law: List[Dict],
    ) -> Dict:

        clause = clause.strip()

        if not clause:

            raise ValueError(
                "Clause cannot be empty."
            )

        prompt = (
            self._build_prompt(
                clause=clause,
                model_result=model_result,
                retrieved_law=retrieved_law,
            )
        )

        try:
            raw_response = groq_chat_completion(
                prompt,
                model=self.model_name,
                temperature=0.1,
                json_mode=True,
                timeout=180,
            )
        except GroqError as error:
            raise RuntimeError(f"Groq request failed: {error}") from error

        ######################################################
        # PARSE JSON
        ######################################################

        try:

            analysis = json.loads(
                raw_response
            )

        except json.JSONDecodeError:
            return _unknown_analysis("The Groq response was not valid JSON.")

        try:
            validated = _LegalAssessment.model_validate(analysis)
        except ValidationError:
            return _unknown_analysis("The Groq response failed schema validation.")

        allowed_sections = {str(item.get("section", "")) for item in retrieved_law}
        cited_sections = {
            item.section
            for item in validated.relevant_sections + validated.irrelevant_or_weak_sections
        }
        if cited_sections - allowed_sections:
            return _unknown_analysis("The Groq response cited a section outside the retrieved context.")

        result = validated.model_dump()
        if model_result is None:
            result["agreement_with_model"] = False
        if not retrieved_law or not validated.relevant_sections:
            result["evidence_sufficient"] = False
            result["human_review_required"] = True
        return result


##############################################################
# BASIC CONNECTION TEST
##############################################################

if __name__ == "__main__":

    llm = GroqLegalLLM()

    print(
        "=" * 70
    )

    print(
        "GROQ LEGAL LLM TEST"
    )

    print(
        "=" * 70
    )

    if llm.check_connection():

        print(
            "\nGroq connection: OK"
        )

        print(
            f"Configured model  : "
            f"{llm.model_name}"
        )

    else:

        print(
            "\nGroq connection: FAILED"
        )

        print(
            "Check GROQ_API_KEY and GROQ_MODEL."
        )


# Preserve the old import name for downstream callers.
LocalLegalLLM = GroqLegalLLM
