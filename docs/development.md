# Development

Create a virtual environment and install the test extras:

```shell
python -m venv .venv
python -m pip install -e ".[test]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

The authoritative mobile implementation currently lives in the private
`bgibbo/shiftplus` repository. Update protocol tests on both sides whenever the
wire contract changes.
