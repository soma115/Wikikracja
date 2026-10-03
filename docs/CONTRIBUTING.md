# Contributing

We welcome contributions! Here's how you can help.

## Reporting Issues

- Use the [GitHub issue tracker](https://github.com/soma115/wikikracja/issues)
- Include steps to reproduce
- Provide error messages and logs
- Mention your environment (OS, Python version, Docker version, etc.)

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (if available)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to your fork (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Development Guidelines

- Follow the project's ruff configuration (`pyproject.toml`)
- Run `.venv\Scripts\python.exe -m ruff check .` and `.venv\Scripts\python.exe -m ruff format --check .` before submitting
- Install and enable both commit and push checks: `.venv\Scripts\python.exe -m pip install pre-commit` and `.venv\Scripts\python.exe -m pre_commit install`
- The regular commit hook runs fast static checks; the pre-push hook runs the complete local CI verification through `scripts\run_tests.py` (including Ruff, Django checks, translations, collectstatic, pytest, Jest, Tailwind, UI guards and Playwright). Ensure Node dependencies, Playwright browsers, Redis and the dedicated E2E account from `.env.local` are available locally.
- To run the same full gate manually use `.venv\Scripts\python.exe scripts\run_tests.py`. To inspect only the legacy change-aware test selection use `.venv\Scripts\python.exe scripts\pre_push_tests.py --dry-run --files chat\services.py`.
- Add comments for complex logic
- Update documentation for new features
- Test your changes locally before submitting
- Keep commits atomic and well-described
