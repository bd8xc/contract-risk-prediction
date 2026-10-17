# CR legal LLM adapter

`local_llm.py` defines the legal analysis response contract and calls the shared root `groq_client.py`. It validates returned JSON, evidence flags, and section references before CR accepts an explanation.
