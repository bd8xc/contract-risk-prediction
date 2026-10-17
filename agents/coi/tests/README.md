# COI tests

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q agents/coi/tests
```

Set `COI_TEST_NEO4J=1` only when running the real Neo4j integration tests against a disposable local database. Other tests cover entity matching, bounded paths, evidence, extraction, API responses, and the optional LE handoff.
