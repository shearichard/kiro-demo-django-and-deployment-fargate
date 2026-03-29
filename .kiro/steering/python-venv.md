# Python Virtual Environment

This project uses a virtual environment located at `.venv/`.

When suggesting or running any Python-related commands (`python`, `pytest`, `manage.py`, `pip`, etc.), always use the venv-relative path instead of the bare command:

- Use `.venv/bin/python` instead of `python`
- Use `.venv/bin/pytest` instead of `pytest`
- Use `.venv/bin/pip` instead of `pip`

Examples:
```bash
.venv/bin/python manage.py migrate
.venv/bin/pytest --tb=short -q
.venv/bin/pip install -r requirements.txt
```
