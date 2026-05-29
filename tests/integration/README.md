# Integration test notes

## `_transport.time.sleep` monkeypatch coupling

Integration tests that exercise retry-exhaustion paths (`test_gitlab_provider.py:848-849, 862-863, 876-877`; exit-4 cases in `test_cli_quiet_json_matrix.py`) reach into `semvertag._transport` and replace its bound `time.sleep` and `random.uniform` references with no-ops:

```python
monkeypatch.setattr(_transport.time, "sleep", lambda *_: None)
monkeypatch.setattr(_transport.random, "uniform", lambda *_: 0.0)
```

This is the established no-sleep pattern. **Two consequences worth knowing before refactoring `_transport.py`:**

- A rename or restructure that moves the `time` / `random` module bindings (e.g., importing `from time import sleep` instead of `import time`) silently breaks the monkeypatch and reintroduces real sleeps. Tests will pass but take seconds longer.
- If you ever add an injected `sleep_fn` / `random_fn` parameter to `RetryingTransport`, update the integration tests to inject via that seam instead of monkeypatching the module — that closes the coupling.

There is no fix required today; this note exists so future `_transport` refactors don't accidentally regress test runtime or behavior.
