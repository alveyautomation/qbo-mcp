# Contributing

Thanks for your interest. Here's how to get involved.

## Issues

If you've hit a bug, a missing tool, or a quirk in production, open an issue with:
- Tool call (input)
- Expected output
- Actual output
- Provider response if applicable (sanitize credentials)

## Pull requests

Small focused PRs welcome. Larger changes (new tools, write endpoints, breaking refactors): please open an issue first to discuss the design.

## Local development

```bash
pip install -e .[dev]
pytest
```

## Code style

- Black for formatting
- Ruff for linting
- Type hints required on public APIs

## Releasing

Maintainers cut releases via `git tag v0.x.y && git push --tags`.
