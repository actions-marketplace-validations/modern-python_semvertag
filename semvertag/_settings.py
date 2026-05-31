import logging
import os
import typing

import pydantic
import pydantic_settings

from semvertag.strategies.branch_prefix import BranchPrefixConfig
from semvertag.strategies.conventional_commits import ConventionalCommitsConfig


_logger: typing.Final = logging.getLogger(__name__)

_GITLAB_TOKEN_ALIASES: typing.Final[tuple[str, ...]] = (
    "SEMVERTAG_GITLAB__TOKEN",
    "SEMVERTAG_TOKEN",
    "CI_JOB_TOKEN",
    "GITLAB_TOKEN",
)
_GITHUB_TOKEN_ALIASES: typing.Final[tuple[str, ...]] = (
    "SEMVERTAG_GITHUB__TOKEN",
    "SEMVERTAG_TOKEN",
    "GITHUB_TOKEN",
)
_PROJECT_ID_ALIASES: typing.Final[tuple[str, ...]] = (
    "SEMVERTAG_PROJECT_ID",
    "CI_PROJECT_ID",
)
_TOKEN_ALIASES_BY_PATH: typing.Final[dict[str, tuple[str, ...]]] = {
    "gitlab.token": _GITLAB_TOKEN_ALIASES,
    "github.token": _GITHUB_TOKEN_ALIASES,
}
_TOP_LEVEL_FIELD_ALIASES: typing.Final[dict[str, tuple[str, ...]]] = {
    "project_id": _PROJECT_ID_ALIASES,
}
_PROVIDER_TO_NESTED_KEY: typing.Final[dict[str, str]] = {
    "gitlab": "gitlab",
    "github": "github",
}
_REQUEST_TIMEOUT_CEILING: typing.Final = 10.0
_ENV_PREFIX: typing.Final = "SEMVERTAG_"
_ENV_NESTED_DELIMITER: typing.Final = "__"
_PROVIDER_ENV_VAR: typing.Final = _ENV_PREFIX + "PROVIDER"


class GitLabConfig(pydantic.BaseModel):
    endpoint: str = "https://gitlab.com"
    token: pydantic.SecretStr = pydantic.Field(default=pydantic.SecretStr(""))


class GitHubConfig(pydantic.BaseModel):
    token: pydantic.SecretStr = pydantic.Field(default=pydantic.SecretStr(""))


class Settings(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix=_ENV_PREFIX,
        env_nested_delimiter=_ENV_NESTED_DELIMITER,
        case_sensitive=False,
        extra="ignore",
    )

    strategy: typing.Literal["branch-prefix", "conventional-commits"] = "branch-prefix"
    provider: typing.Literal["gitlab", "github", "bitbucket"] = "gitlab"
    default_branch: str | None = None
    request_timeout: float = pydantic.Field(default=8.0, gt=0)
    project_id: int | None = pydantic.Field(default=None)
    quiet: bool = pydantic.Field(default=False)
    gitlab: GitLabConfig = pydantic.Field(default_factory=GitLabConfig)
    github: GitHubConfig = pydantic.Field(default_factory=GitHubConfig)
    branch_prefix: BranchPrefixConfig = pydantic.Field(default_factory=BranchPrefixConfig)
    conventional_commits: ConventionalCommitsConfig = pydantic.Field(default_factory=ConventionalCommitsConfig)

    @pydantic.model_validator(mode="before")
    @classmethod
    def _inject_token_aliases(cls, data: typing.Any) -> typing.Any:  # noqa: ANN401
        if not isinstance(data, dict):
            return data
        provider: typing.Final = _resolve_active_provider(data)
        nested_key: typing.Final = _PROVIDER_TO_NESTED_KEY.get(provider)
        if nested_key is None:
            return data
        aliases: typing.Final = _TOKEN_ALIASES_BY_PATH.get(f"{nested_key}.token")
        if aliases is None:
            return data
        _inject_token(data, nested_key, aliases)
        return data

    @pydantic.model_validator(mode="before")
    @classmethod
    def _inject_top_level_aliases(cls, data: typing.Any) -> typing.Any:  # noqa: ANN401
        if not isinstance(data, dict):
            return data
        for field_name, aliases in _TOP_LEVEL_FIELD_ALIASES.items():
            if field_name in data and data[field_name] is not None:
                continue
            found = _find_aliased_env(aliases)
            if found is None:
                continue
            _matched_alias, value = found
            data[field_name] = value
        return data

    @pydantic.field_validator("request_timeout")
    @classmethod
    def _clamp_request_timeout(cls, value: float) -> float:
        if value > _REQUEST_TIMEOUT_CEILING:
            _logger.warning(
                "request_timeout=%.3f exceeds ceiling %.1f; clamping to %.1f",
                value,
                _REQUEST_TIMEOUT_CEILING,
                _REQUEST_TIMEOUT_CEILING,
            )
            return _REQUEST_TIMEOUT_CEILING
        return value


def _resolve_active_provider(data: dict[str, typing.Any]) -> str:
    raw = data.get("provider")
    if raw is None:
        raw = _find_env_value((_PROVIDER_ENV_VAR,))
    if raw is None:
        raw = "gitlab"
    return str(raw).lower()


def _inject_token(data: dict[str, typing.Any], nested_key: str, aliases: tuple[str, ...]) -> None:
    nested: typing.Final = data.setdefault(nested_key, {})
    if not isinstance(nested, dict) or "token" in nested:
        return
    found: typing.Final = _find_aliased_env(aliases)
    if found is None:
        return
    _matched_alias, value = found
    nested["token"] = value


def _find_aliased_env(candidates: tuple[str, ...]) -> tuple[str, str] | None:
    env_lower_to_value: typing.Final = {key.lower(): value for key, value in os.environ.items()}
    for alias in candidates:
        value = env_lower_to_value.get(alias.lower())
        if value:
            return alias, value
    return None


def _find_env_value(candidates: tuple[str, ...]) -> str | None:
    found: typing.Final = _find_aliased_env(candidates)
    if found is None:
        return None
    return found[1]


def apply_cli_overlay(
    settings: Settings,
    overrides: dict[str, tuple[typing.Any, str]],
) -> Settings:
    update_top, nested_updates = _split_overrides(settings, overrides)
    for head, leaf_updates in nested_updates.items():
        update_top[head] = _revalidate_nested(settings, head, leaf_updates)

    copied: typing.Final = settings.model_copy(update=update_top, deep=True)
    raw_data: typing.Final = {name: getattr(copied, name) for name in type(copied).model_fields}
    new_settings: typing.Final = type(copied).model_validate(raw_data)
    return new_settings


def _split_overrides(
    settings: Settings,
    overrides: dict[str, tuple[typing.Any, str]],
) -> tuple[dict[str, typing.Any], dict[str, dict[str, typing.Any]]]:
    update_top: dict[str, typing.Any] = {}
    nested_updates: dict[str, dict[str, typing.Any]] = {}
    settings_fields: typing.Final = type(settings).model_fields

    for dotted_key, (value, _flag_detail) in overrides.items():
        if "." in dotted_key:
            head, _, leaf = dotted_key.partition(".")
            if "." in leaf:
                msg = f"CLI overlay key '{dotted_key}' exceeds nesting depth 2."
                raise ValueError(msg)
            if head not in settings_fields:
                msg = f"Unknown CLI overlay target: {head!r}."
                raise ValueError(msg)
            nested_updates.setdefault(head, {})[leaf] = value
        else:
            if dotted_key not in settings_fields:
                msg = f"Unknown CLI overlay target: {dotted_key!r}."
                raise ValueError(msg)
            update_top[dotted_key] = value
    return update_top, nested_updates


def _revalidate_nested(
    settings: Settings,
    head: str,
    leaf_updates: dict[str, typing.Any],
) -> pydantic.BaseModel:
    nested: typing.Final = getattr(settings, head)
    if not isinstance(nested, pydantic.BaseModel):
        msg = f"CLI overlay target '{head}' is not a pydantic BaseModel."
        raise TypeError(msg)
    nested_fields: typing.Final = type(nested).model_fields
    for leaf in leaf_updates:
        if leaf not in nested_fields:
            msg = f"Unknown CLI overlay target: {head}.{leaf!r}."
            raise ValueError(msg)
    nested_data: typing.Final = {name: getattr(nested, name) for name in nested_fields}
    nested_data.update(leaf_updates)
    return type(nested).model_validate(nested_data)
