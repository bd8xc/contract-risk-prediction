# Root integration tests

Run from the repository root with `python -m pytest -q`. `pytest.ini` selects the maintained root, COI, LE, and CL suites while excluding old CR experiment scripts that execute training-file reads during collection. These tests cover the web coordinator, document extraction, CR evidence validation, unified agent and ingestion routes, and indexed-document replacement.
