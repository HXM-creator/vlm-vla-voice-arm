.PHONY: install test lint format run-sim record train-act train-smolvla eval clean

install:
	pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check src tests

format:
	ruff format src tests

run-sim:
	python -m voice_arm.app.orchestrator --config configs/sim.yaml

record:
	bash scripts/record_data.sh

train-act:
	bash scripts/train_act.sh

train-smolvla:
	bash scripts/train_smolvla.sh

eval:
	bash scripts/eval.sh

clean:
	rm -rf outputs/ __pycache__/ .pytest_cache/ .ruff_cache/
