# Contributing to Sora Trading Bot

Thank you for your interest! This is a personal-use project, but contributions, suggestions, and bug reports are welcome.

## How to Contribute

1. **Fork** the repository
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes**
4. **Run tests**: `pytest tests/ -v`
5. **Commit** with a clear, descriptive message
6. **Push** and open a **Pull Request**

## Development Setup

See [GETTING_STARTED.md](GETTING_STARTED.md) for full setup instructions:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
# Edit .env with your API keys
python -c "from db.store import init_db; init_db()"
```

## Code Style

- Follow **PEP 8** conventions
- Use **type hints** for function signatures
- Use **async/await** for I/O-bound operations
- Keep functions focused and single-purpose
- Use **descriptive variable names** — avoid single-letter names (except for standard math)
- Add **docstrings** for public functions and classes
- Use **f-strings** for string formatting

## Testing

- All changes must pass existing tests: `pytest tests/ -v`
- Add tests for new features when possible (test files go in `tests/`)
- The project uses `pytest` + `pytest-asyncio` (asyncio_mode = auto)
- Tests requiring API keys will be skipped if keys are not set — this is expected

## Pull Request Checklist

Before submitting your PR:

- [ ] Tests pass (`pytest tests/ -v`)
- [ ] No API keys, tokens, or secrets committed
- [ ] No `.env` files committed
- [ ] No `*.db` or `*.log` files committed
- [ ] Code follows existing project patterns
- [ ] Docstrings added for new public functions
- [ ] Changes are scoped to a single feature/bugfix

## Reporting Issues

### Bug Reports

Open a GitHub issue with:

- A clear title and description
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS
- Relevant log output

### Feature Requests

Open a GitHub issue with:

- What problem you're trying to solve
- Proposed solution
- Any alternative solutions considered
- Additional context or examples

## Code of Conduct

Be respectful, constructive, and collaborative. This is a small project — treat others how you'd like to be treated.
