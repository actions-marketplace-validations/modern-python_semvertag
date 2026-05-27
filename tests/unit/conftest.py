import os
import typing

import pytest


_EXPLICIT_ENV_VARS: typing.Final = (
    "SEMVERTAG_TOKEN",
    "SEMVERTAG_STRATEGY",
    "SEMVERTAG_PROVIDER",
    "SEMVERTAG_DEFAULT_BRANCH",
    "SEMVERTAG_REQUEST_TIMEOUT",
    "SEMVERTAG_GITLAB__ENDPOINT",
    "SEMVERTAG_GITLAB__TOKEN",
    "SEMVERTAG_GITHUB__TOKEN",
    "CI_JOB_TOKEN",
    "GITLAB_TOKEN",
    "GITHUB_TOKEN",
    "BITBUCKET_TOKEN",
)


@pytest.fixture
def clean_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _EXPLICIT_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    for key in list(os.environ):
        if key.startswith("SEMVERTAG_"):
            monkeypatch.delenv(key, raising=False)
