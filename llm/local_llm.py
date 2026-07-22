import json
from typing import Dict, List

import requests


class LocalLegalLLM:
    """
    Local LLM reasoning layer for contract-risk analysis.

    The LLM does NOT replace LegalBERT and does NOT independently
    retrieve law.

    It receives:

        1. Original contract clause
        2. LegalBERT risk prediction
        3. Retrieved Indian statutory provisions

    It then produces a grounded explanation.

    Ollama is expected to run locally.
    """

    def __init__(
            self,
            model_name="qwen2.5:1.5b",
            base_url="http://localhost:11434",
        ):
        self.model_name = model_name

        self.base_url = (
            base_url.rstrip("/")
        )

        self.generate_url = (
            f"{self.base_url}/api/generate"
        )

    ##########################################################
    # CHECK CONNECTION
    ##########################################################

    def check_connection(self):

        try:

            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=10,
            )

            response.raise_for_status()

            return True

        except requests.RequestException:

            return False

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
        model_result: Dict,
        retrieved_law: List[Dict],
    ) -> str:

        model_context = (
            self._format_model_result(
                model_result
            )
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
2. A risk signal produced by a fine-tuned LegalBERT classifier.
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
        model_result: Dict,
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

        payload = {

            "model":
                self.model_name,

            "prompt":
                prompt,

            "stream":
                False,

            "format":
                "json",

            "options": {

                # Low temperature is preferable for
                # grounded legal analysis.
                "temperature":
                    0.1,

            },
        }

        try:

            response = requests.post(
                self.generate_url,
                json=payload,
                timeout=180,
            )

            response.raise_for_status()

        except requests.RequestException as error:

            raise RuntimeError(
                "Could not communicate with "
                "the local Ollama server. "
                "Make sure Ollama is running "
                "and the requested model is installed."
            ) from error

        data = response.json()

        raw_response = data.get(
            "response",
            ""
        ).strip()

        if not raw_response:

            raise RuntimeError(
                "Local LLM returned an "
                "empty response."
            )

        ######################################################
        # PARSE JSON
        ######################################################

        try:

            analysis = json.loads(
                raw_response
            )

        except json.JSONDecodeError:

            # Preserve raw output if model ever fails
            # strict JSON generation.

            return {

                "assessed_risk":
                    "Unknown",

                "agreement_with_model":
                    False,

                "summary":
                    (
                        "The local LLM response "
                        "could not be parsed."
                    ),

                "risk_reasoning":
                    raw_response,

                "relevant_sections":
                    [],

                "irrelevant_or_weak_sections":
                    [],

                "contractual_concern":
                    "Unable to parse analysis.",

                "suggested_mitigation":
                    (
                        "Manual review recommended."
                    ),

                "human_review_required":
                    True,

                "evidence_sufficient":
                    False,
            }

        return analysis


##############################################################
# BASIC CONNECTION TEST
##############################################################

if __name__ == "__main__":

    llm = LocalLegalLLM()

    print(
        "=" * 70
    )

    print(
        "LOCAL LEGAL LLM TEST"
    )

    print(
        "=" * 70
    )

    if llm.check_connection():

        print(
            "\nOllama connection: OK"
        )

        print(
            f"Configured model  : "
            f"{llm.model_name}"
        )

    else:

        print(
            "\nOllama connection: FAILED"
        )

        print(
            "Make sure Ollama is running."
        )