# Contributing

Small, reviewable changes are preferred.

## Local checks

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests examples
```

Please add or update tests for behavior changes. Authorization semantics should remain deterministic: model output must never be treated as permission to expand a `Policy`.
