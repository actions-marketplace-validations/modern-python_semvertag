import typing

import pytest

from semvertag import ioc
from semvertag._errors import ConfigError
from semvertag._settings import Settings
from semvertag.strategies.branch_prefix import BranchPrefixStrategy
from semvertag.strategies.conventional_commits import ConventionalCommitsStrategy


_StrategyName = typing.Literal["branch-prefix", "conventional-commits"]
_ProviderName = typing.Literal["gitlab", "github", "bitbucket"]


def _settings(
    *,
    strategy: _StrategyName = "branch-prefix",
    provider: _ProviderName = "gitlab",
) -> Settings:
    return Settings(project_id=999, strategy=strategy, provider=provider)


def test_build_container_resolves_branch_prefix_strategy_by_default() -> None:
    settings: typing.Final = _settings(strategy="branch-prefix")
    with ioc.build_container(settings) as container:
        strategy = container.resolve_provider(ioc.StrategiesGroup.current_strategy)
        assert isinstance(strategy, BranchPrefixStrategy)
        assert strategy.name == "branch-prefix"


def test_build_container_resolves_conventional_commits_strategy_when_settings_strategy_is_cc() -> None:
    settings: typing.Final = _settings(strategy="conventional-commits")
    with ioc.build_container(settings) as container:
        strategy = container.resolve_provider(ioc.StrategiesGroup.current_strategy)
        assert isinstance(strategy, ConventionalCommitsStrategy)
        assert strategy.name == "conventional-commits"


def test_named_strategy_factories_resolve_to_their_concrete_types_regardless_of_settings() -> None:
    settings: typing.Final = _settings(strategy="conventional-commits")
    with ioc.build_container(settings) as container:
        bp = container.resolve_provider(ioc.StrategiesGroup.branch_prefix_strategy)
        cc = container.resolve_provider(ioc.StrategiesGroup.conventional_commits_strategy)
        assert isinstance(bp, BranchPrefixStrategy)
        assert isinstance(cc, ConventionalCommitsStrategy)


@pytest.mark.parametrize("provider", ["github", "bitbucket"])
def test_build_container_raises_config_error_when_provider_is_not_gitlab(
    provider: _ProviderName,
) -> None:
    settings: typing.Final = _settings(provider=provider)
    with pytest.raises(ConfigError, match=f"Provider {provider!r} not yet supported"):
        ioc.build_container(settings)
