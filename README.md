# LDI Pipeline Project Structure

Initial project structure for the Legal Document Intelligence (LDI) pipeline has been scaffolded as follows:

```
ldi/
	app/
		__init__.py
		main.py
	config/
		settings.py
	ingestion/
		__init__.py
		pdf_loader.py
		docx_loader.py
		cleaner.py
	chunking/
		__init__.py
		clause_splitter.py
		normalizer.py
	embeddings/
		__init__.py
		embedder.py
		vector_store.py
	classification/
		__init__.py
		risk_classifier.py
	conflict_detection/
		__init__.py
		entity_extractor.py
		conflict_rules.py
	explainability/
		__init__.py
		explain.py
	schemas/
		__init__.py
		outputs.py
	tests/
		__init__.py
	pipeline.py
requirements/
	ldi.txt
```

To install dependencies:

```sh
python -m venv venv
venv\Scripts\activate  # On Windows
pip install -r requirements/ldi.txt
python -m spacy download en_core_web_lg
```

---
Initial commit: LDI scaffold and requirements.
# legal-risk-compliance-ai


To run it -
 uvicorn ldi.app.main:app --reload        