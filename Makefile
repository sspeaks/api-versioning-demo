# Same commands locally and in CI.
PY := uv run python
BASE ?= main

.PHONY: install tools run openapi drift breaking changelog lint test check

install:            ## install Python deps (uv workspace)
	uv sync

tools:              ## install pinned oasdiff into ./.bin
	./tools/install-oasdiff.sh

run:                ## run the orders service on :8000  (/v1/docs, /v2/docs)
	uv run uvicorn orders.main:app --reload

openapi:            ## regenerate committed OpenAPI contracts from code
	$(PY) tools/api_contract.py export

drift:              ## fail if committed contracts don't match the code
	$(PY) tools/api_contract.py drift

breaking:           ## fail on breaking changes vs $(BASE)  (make breaking BASE=origin/main)
	$(PY) tools/api_contract.py breaking --base $(BASE)

changelog:          ## markdown changelog of contract changes vs $(BASE)
	$(PY) tools/api_contract.py changelog --base $(BASE)

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest -q

check: lint test drift breaking  ## everything CI runs
