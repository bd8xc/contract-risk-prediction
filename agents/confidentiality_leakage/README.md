# Confidentiality Leakage Agent

## 1. Purpose

The Confidentiality Leakage Agent is a lightweight Data Loss Prevention (DLP) engine for legal documents. It identifies information that may be confidential, personal, sensitive personal, or operationally important.

The agent sits **on top of the existing Legal Document Intelligence (LDI) pipeline**. It consumes clause text already produced by LDI. It does not ingest PDF or DOCX files, split clauses, generate embeddings, write to ChromaDB, or perform search.

The agent answers questions such as:

- Does this clause contain a structured identifier or credential?
- Does it contain personal or sensitive personal information?
- Does it describe a confidential business asset?
- Does it describe collecting, storing, sharing, or transferring personal data?
- Does it contain a real person, organization, location, date, or money reference that is useful as context?
- What risk level should the document receive based on the actual data types detected?

## 2. Important Terminology and Full Forms

| Term | Full form | Meaning in this project |
| --- | --- | --- |
| LDI | Legal Document Intelligence | The existing upstream pipeline that extracts and chunks legal clauses and indexes them. |
| DLP | Data Loss Prevention | Detection and prevention of sensitive information exposure. |
| PII | Personally Identifiable Information | Information that identifies or describes a person, such as email, phone, salary, or address. |
| SPI / sensitive personal data | Sensitive Personal Information | Highly regulated personal information, such as medical, biometric, religious, or genetic information. |
| NER | Named Entity Recognition | NLP detection of names, organizations, places, money, and dates. |
| NLP | Natural Language Processing | Software processing of human language. |
| ORG | Organization | A company, institution, or other organization detected by NER. |
| GPE | Geopolitical Entity | A country, state, city, or other political geography detected by NER. |
| LOC | Location | A non-political place detected by NER. |
| API | Application Programming Interface | A programmatic interface; API keys are structured secrets. |
| JWT | JSON Web Token | A token formatted as three dot-separated encoded sections. |
| PAN | Permanent Account Number | An Indian tax identifier, normally five letters, four digits, and one letter. |
| GST | Goods and Services Tax | An Indian indirect-tax registration identifier. |
| IFSC | Indian Financial System Code | An Indian bank-branch identifier. |
| IBAN | International Bank Account Number | An internationally standardized bank account identifier. |
| SWIFT | Society for Worldwide Interbank Financial Telecommunication | A bank identifier code format. |
| UPI | Unified Payments Interface | A payment address format such as `name@bank`. |
| IP | Internet Protocol | A network address such as `192.168.1.10`. |
| MAC | Media Access Control | A network interface hardware address. |
| OAuth | Open Authorization | A delegated authorization and token protocol. |
| AWS | Amazon Web Services | Cloud credentials include AWS access keys. |
| Pydantic | Python data validation library | Used to define and validate API request and response models. |
| FastAPI | Python web API framework | Used by the application router. |

## 3. High-Level Architecture

```text
PDF/DOCX
	|
	v
Existing LDI pipeline
	ingestion -> extraction -> clause splitting -> embeddings -> ChromaDB -> search
																												|
																												| existing clause rows
																												v
																			ConfidentialityLeakageAgent
																												|
				+-------------------+------------------+--------+------------------+
				|                   |                  |                           |
	 RegexDetector       PIIDetector    SensitivePersonalDetector   ConfidentialBusinessDetector
				|                   |                  |                           |
				+-------------------+------------------+---------------------------+
																												|
																			NERDetector (context only)
																			ProcessingActivityDetector
																												|
													 classify -> deduplicate -> score -> API response
```

## 4. Execution Flow

1. `POST /confidentiality/analyze` receives a `doc_id`.
2. The agent asks `ClauseVectorStore` for the already-indexed clauses for that document.
3. Each clause supplies `text`, and optionally `clause_id` and `section`.
4. Five information detectors analyze the clause independently.
5. The processing detector separately identifies data-handling activities.
6. `classifier.py` adds sensitivity, category metadata, and clause traceability.
7. Overlapping or duplicate findings are reduced, with stronger non-NER findings preferred.
8. `scorer.py` calculates a document score from explicit sensitivity classes and processing activity count.
9. `schemas.py` validates the response.
10. The router returns the report. Values are currently returned in raw form for development and inspection.

## 5. Package Structure

```text
agents/confidentiality_leakage/
|-- __init__.py
|-- agent.py
|-- router.py
|-- schemas.py
|-- classifier.py
|-- scorer.py
|-- masker.py
|-- regex_detector.py       compatibility import
|-- ner_detector.py         compatibility import
|-- content_detector.py     compatibility import
|-- README.md
`-- detectors/
		|-- __init__.py
		|-- patterns.py
		|-- dictionaries.py
		|-- regex_detector.py
		|-- pii_detector.py
		|-- sensitive_personal_detector.py
		|-- confidential_business_detector.py
		|-- processing_activity_detector.py
		`-- ner_detector.py
```

## 6. File-by-File Responsibilities

### `agent.py`

`ConfidentialityLeakageAgent` is the coordinator. It owns the detector instances, loads clauses from the existing vector store, passes metadata to detectors, aggregates results, invokes classification and scoring, and builds `ConfidentialityReport`.

It supports two modes:

```python
agent.analyze("contract.docx")
agent.analyze("test-doc", clauses=[{"clause_id": "1", "section": "Contact", "text": "..."}])
```

The second form is useful for unit tests and integrations that already have LDI clause output.

### `router.py`

Defines the existing FastAPI endpoints under the `/confidentiality` prefix:

- `GET /confidentiality/documents` lists indexed document ids.
- `POST /confidentiality/analyze` analyzes one indexed document.

Lookup failures are returned as HTTP 404 responses. The router does not perform detection itself.

### `schemas.py`

Defines the Pydantic models:

- `ClauseInput`: optional input representation for an LDI clause.
- `ConfidentialityAnalyzeRequest`: requires `doc_id`.
- `SensitiveFinding`: one normalized finding with type, raw value, source, sensitivity, category, offsets, and clause traceability.
- `ConfidentialityReport`: document-level result.
- `DocumentIndexItem`: indexed document metadata.

`start` and `end` are character offsets within the individual clause text, not offsets in the original DOCX file.

### `classifier.py`

Maps every detector-emitted finding type to one explicit sensitivity class. The policy sets are disjoint; a type cannot receive a different class because of conditional ordering:

- `CRITICAL`: credentials, passwords, connection strings, bank accounts, credit cards, core medical data, biometrics, genetic information, trade secrets, and confidential financial information.
- `HIGH`: PAN, Aadhaar, IBAN, passport, driving licence, GST, salary, health insurance, selected sensitive-personal categories, customer/supplier lists, and research.
- `MEDIUM`: email, phone, IP address, address, postal code, labelled personal attributes, technical identifiers, and selected confidential business categories.
- `LOW`: confidential contract mentions and processing-activity values if they are passed through the classifier.
- `CONTEXT_DEPENDENT`: PERSON, ORG, GPE, LOC, MONEY, and DATE. These remain findings for traceability but contribute zero to risk scoring.

Unknown detector types are deliberately retained as `LOW` until their detector contract is reviewed. This keeps the API stable without silently treating new types as context or allowing them to inflate risk.

The classifier removes duplicate findings and resolves NER-versus-structured overlaps. Distinct overlapping structured findings, such as an address containing a postal code, are preserved. A structured detector result is preferred over an NER result for the same span.

### `scorer.py`

Calculates a bounded score from 0 to 100. Context-only findings contribute zero. The score uses saturating components so repeated matches do not grow without limit:

```text
critical component   = 55 * (1 - exp(-critical_count / 1.5))
high component       = 30 * (1 - exp(-high_count / 2.0))
medium component     = 15 * (1 - exp(-medium_count / 4.0))
processing component = 12 * (1 - exp(-activity_count / 8.0))
low component        = min(5, low_count * 0.5)

score = round(min(100, sum of components))
```

Risk levels are:

- `0-19`: `LOW`
- `20-49`: `MEDIUM`
- `50-74`: `HIGH`
- `75-100`: `CRITICAL`

Processing activity is scored as a bounded medium-risk signal. It indicates data handling, but it does not prove that a value was leaked.

### `masker.py`

Contains the previous masking helper for emails, numbers, IP addresses, names, organizations, and confidentiality labels. The agent does not currently call it because raw values were requested for development. Before production exposure, either call `mask_value` in `agent.py` or enforce redaction at an API gateway.

### Compatibility modules

The root-level `regex_detector.py`, `ner_detector.py`, and `content_detector.py` re-export the new detector classes and old function names. This preserves existing imports while the implementation lives under `detectors/`.

## 7. Detector Details

Every detector exposes the same interface:

```python
detect(text, metadata) -> list[dict]
```

The normalized base result is:

```json
{
	"type": "EMAIL",
	"value": "john.doe@example.com",
	"start": 10,
	"end": 31,
	"source": "regex",
	"category": "personal_data"
}
```

### 7.1 `RegexDetector`

File: `detectors/regex_detector.py`

Regex is used only for structured values. Patterns are centralized in `detectors/patterns.py`, preventing duplicated expressions.

Supported types include:

- Contact and identity: email, phone, PAN, Aadhaar, passport, driving licence, GST, IFSC, bank account, IBAN, SWIFT, UPI.
- Network: IP address and MAC address.
- Business identifiers: PIN/postal code, employee ID, vendor ID, invoice ID.
- Secrets: API key, JWT, private key, access token, OAuth token, secret key, database password, connection string, AWS key, Azure key, Google API key.
- Payment: credit card and debit-card-like numbers, with Luhn validation for card numbers.

The detector uses format boundaries and nearby labels for ambiguous values. PAN, Aadhaar, passport, GST, IFSC, and IBAN candidates require nearby identifier or banking context; IP addresses require network context; phone numbers require contact context or an international prefix. SWIFT/BIC matches require an explicit SWIFT/BIC label or a digit in the code's location/branch portion, preventing ordinary uppercase contract words from matching. Postal codes require nearby address, PIN, postal, ZIP, or office wording. Credit-card candidates must pass the Luhn checksum.

### 7.2 `PIIDetector`

File: `detectors/pii_detector.py`

PII rules are deliberately label-driven to avoid treating ordinary legal words as personal data. It detects labelled:

- DOB or date of birth
- Age
- Gender or sex
- Nationality or citizenship
- Residential, home, registered, or mailing address
- Salary, compensation, remuneration, or pay
- Employee number
- Payroll ID
- Emergency contact or next of kin
- Marital status
- Dependents or dependent information

For example, `salary: 120000` is detected, while every number in a contract is not treated as salary. Labelled address matches require a numeric street-style value, so an introduction that only says an office is located in a country is not treated as an address.

### 7.3 `SensitivePersonalDetector`

File: `detectors/sensitive_personal_detector.py`

Uses the controlled vocabulary in `dictionaries.py` to identify:

- Medical history, medical records, and health history
- Diagnosis and clinical conditions
- Prescriptions, medication, and treatment
- Health or medical insurance
- Blood group or blood type
- Biometrics, fingerprints, retina, iris scans, and face ID
- Genetic information and DNA
- Disability
- Religion and religious affiliation
- Political affiliation
- Sexual orientation

These findings are categorized as `sensitive_personal_data`. Several highly sensitive types are classified as `CRITICAL`.

Ambiguous terms such as `treatment` and `medication` require nearby medical context; contractual treatment of a dispute is not sufficient.

### 7.4 `ConfidentialBusinessDetector`

File: `detectors/confidential_business_detector.py`

Uses `BUSINESS_CONFIDENTIAL` vocabulary from `dictionaries.py` to detect:

- Trade secrets, proprietary information, source code, and algorithms
- Financial statements, forecasts, revenue, margins, pricing, and budgets
- Customer, client, supplier, and vendor lists
- Business plans, internal strategy, product roadmaps, and acquisition plans
- Research and development, research data, and patent information
- Confidential contracts and non-public contract terms
- Encryption keys, API secrets, passwords, and credentials

Results are categorized as `business_confidential`. A detector match means the clause discusses the asset; it does not by itself prove that the asset has been disclosed outside its authorized audience.

Ambiguous financial terms such as `pricing`, `revenue`, and `budget` require confidentiality context or an informative phrase such as `pricing model`, `revenue forecast`, or `financial statement`.

### 7.5 `ProcessingActivityDetector`

File: `detectors/processing_activity_detector.py`

Detects language describing personal-data handling:

`collect`, `store`, `retain`, `delete`, `erase`, `share`, `transfer`, `transmit`, and `process`, including common inflected forms. An action must have nearby data language such as `personal data`, `records`, `details`, or `bank`; party names and non-data actions such as transferring title are ignored. `third party` is reported only when a data-handling action is present.

These results are not included in ordinary `findings`. They appear in `processing_activity` and are counted in `summary.processing_activities`. Each activity has its clause id and section, plus an `activity` normalized to lowercase.

### 7.6 `NERDetector`

File: `detectors/ner_detector.py`

NER means Named Entity Recognition. When available, the detector loads spaCy model `en_core_web_sm` and accepts only:

`PERSON`, `ORG`, `GPE`, `LOC`, `MONEY`, and `DATE`.

Validation heuristics reject legal boilerplate and generic roles such as `Company`, `Employee`, `Vendor`, `Applicable Law`, `Cause`, `Agreement`, `Schedule`, `Section`, `Party`, `Force Majeure`, `Neither Party`, and `Disclosing Party`. Placeholder-style tokens are rejected through centralized placeholder and role rules rather than document-specific exceptions. Person candidates with address-like street context and deadline phrases such as `within thirty days` are filtered, while genuine people, companies, locations, and calendar dates remain eligible.

Additional checks include:

- A person generally needs at least two name-like tokens.
- Organization values cannot be empty or obvious boilerplate.
- Money must contain a number or currency symbol.
- Locations must be non-empty and plausible.

If spaCy is not installed, a narrow fallback recognizes obvious two-token person names and organization names with corporate suffixes. NER is context only and contributes zero to risk.

## 8. Central Configuration Files

### `detectors/patterns.py`

Contains all structured regular expressions. Add a new structured identifier here, then map its output type and risk class in `classifier.py`.

### `detectors/dictionaries.py`

Contains controlled vocabularies for sensitive personal data, business confidential data, processing activities, and legal boilerplate. Add domain terms here rather than embedding them inside detector logic.

## 9. Response Format

Example:

```json
{
	"doc_id": "Founders Employment Agreement T1.docx",
	"sensitive_data_detected": true,
	"risk_score": 45,
	"risk_level": "MEDIUM",
	"total_findings": 3,
	"high_sensitivity_count": 1,
	"medium_sensitivity_count": 1,
	"context_dependent_count": 0,
	"summary": {
		"personal_data": 2,
		"sensitive_personal_data": 1,
		"business_confidential": 0,
		"processing_activities": 2
	},
	"findings": [
		{
			"type": "EMAIL",
			"value": "john.doe@example.com",
			"source": "regex",
			"sensitivity": "MEDIUM",
			"category": "personal_data",
			"clause_id": "1",
			"section": "Contacts",
			"start": 8,
			"end": 28
		}
	],
	"processing_activity": [
		{
			"type": "PROCESSING_ACTIVITY",
			"value": "store",
			"activity": "store",
			"source": "processing",
			"category": "processing_activity",
			"clause_id": "1",
			"section": "Contacts",
			"start": 64,
			"end": 69
		}
	]
}
```

`total_findings` includes context findings such as ORG, GPE, LOC, and DATE. Those findings are useful for review but do not increase the score. The category summary contains personal, sensitive personal, and business findings plus the separate activity count.

## 10. Understanding a Document Score

For a document containing 49 context entities, one high-sensitivity salary finding, one person entity, two low findings, and 22 processing activities:

- The 49 ORG/GPE/LOC/DATE entities contribute zero.
- The person entity is context-only and contributes zero.
- The salary contributes through the high component.
- The low findings add only a small capped amount.
- The 22 processing activities add a bounded handling-risk component.
- The final score is rounded and mapped to a risk level.

The score expresses detection severity and handling exposure. It is not a legal conclusion, a breach determination, or a substitute for a privacy impact assessment.

## 11. LDI Integration

The agent uses:

```python
ClauseVectorStore.get_document_clauses(doc_id)
```

Each returned row should contain:

```json
{
	"clause_id": "P4_part11",
	"section": "Document",
	"text": "The processor may collect and store personal data..."
}
```

The agent does not call document loaders, clause splitters, embedding code, or Chroma indexing code. This boundary prevents confidentiality analysis from changing LDI behavior.

## 12. API Usage

List indexed documents:

```http
GET /confidentiality/documents
```

Analyze one document:

```http
POST /confidentiality/analyze
Content-Type: application/json

{"doc_id": "Founders Employment Agreement T1.docx"}
```

The document must already be indexed by LDI. Otherwise the endpoint returns HTTP 404.

## 13. Limitations

- Regex recognizes formats; it cannot prove that an identifier is valid in the issuing system.
- Label-driven PII rules can miss unlabelled information.
- Keyword detection can miss synonyms and can match a term without understanding its legal scope.
- Processing activity detection identifies handling language but does not determine whether processing is lawful.
- spaCy quality depends on `en_core_web_sm` and the language of the document.
- Findings are clause-local; the agent does not yet resolve the same person or account across clauses.
- Raw values are intentionally exposed during development. This is not appropriate for an unrestricted production API.
- `total_findings` can be larger than the meaningful privacy/business counts because it includes context findings.

## 14. Future Improvements

- Add tenant-configurable policies and jurisdiction-specific rules.
- Add confidence scores and evidence snippets.
- Add cross-clause entity resolution and document-level deduplication.
- Add secure redaction, audit logging, and role-based access to raw values.
- Add detector metrics, feedback, and regression datasets.
- Add multilingual models and configurable spaCy pipelines.
- Add explicit disclosure-context detection, such as external recipient, unauthorized sharing, or public exposure.

## 15. Developer Notes

- Keep detectors independent and return normalized findings.
- Put regex definitions only in `patterns.py`.
- Put reusable vocabulary only in `dictionaries.py`.
- Keep risk policy in `classifier.py` and `scorer.py`, not inside detectors.
- Preserve `clause_id`, `section`, `start`, and `end` for traceability.
- Add focused tests for every new identifier or vocabulary group.
- Install spaCy and the model only when NER enrichment is needed; deterministic detectors work without spaCy.
- Before production deployment, restore masking or introduce an authenticated, audited redaction boundary.
