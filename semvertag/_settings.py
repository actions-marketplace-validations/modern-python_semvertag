import logging
import typing

import pydantic
import pydantic_settings

from semvertag.strategies.branch_prefix import BranchPrefixConfig
from semvertag.strategies.conventional_commits import ConventionalCommitsConfig


_logger: typing.Final = logging.getLogger(__name__)

_REQUEST_TIMEOUT_CEILING: typing.Final = 10.0
_ENV_PREFIX: typing.Final = "SEMVERTAG_"
_ENV_NESTED_DELIMITER: typing.Final = "__"


class GitLabConfig(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix="SEMVERTAG_GITLAB__",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    endpoint: str = "https://gitlab.com"
    token: pydantic.SecretStr = pydantic.Field(
        default=pydantic.SecretStr(""),
        validation_alias=pydantic.AliasChoices(
            "SEMVERTAG_GITLAB__TOKEN",
            "SEMVERTAG_TOKEN",
            "CI_JOB_TOKEN",
            "GITLAB_TOKEN",
        ),
    )


class GitHubConfig(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix="SEMVERTAG_GITHUB__",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    token: pydantic.SecretStr = pydantic.Field(
        default=pydantic.SecretStr(""),
        validation_alias=pydantic.AliasChoices(
            "SEMVERTAG_GITHUB__TOKEN",
            "SEMVERTAG_TOKEN",
            "GITHUB_TOKEN",
        ),
    )


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
    project_id: int | None = pydantic.Field(
        default=None,
        validation_alias=pydantic.AliasChoices("SEMVERTAG_PROJECT_ID", "CI_PROJECT_ID"),
    )
    quiet: bool = pydantic.Field(default=False)
    gitlab: GitLabConfig = pydantic.Field(default_factory=GitLabConfig)
    github: GitHubConfig = pydantic.Field(default_factory=GitHubConfig)
    branch_prefix: BranchPrefixConfig = pydantic.Field(default_factory=BranchPrefixConfig)
    conventional_commits: ConventionalCommitsConfig = pydantic.Field(default_factory=ConventionalCommitsConfig)

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
