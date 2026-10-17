# COI API

`main.py` creates the standalone FastAPI app. `routes.py` exposes COI checking and optional COI-to-LE assessment; `schemas.py` validates requests and responses. Start from the repository root with `python -m uvicorn coi.api.main:app` after installing root requirements. This API shares the root `.env`.
