import typing

from semvertag import ioc
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


def test_container_resolves_branch_prefix_strategy_by_default() -> None:
    settings: typing.Final = _settings(strategy="branch-prefix")
    with ioc.container:
        ioc.container.set_context(Settings, settings)
        strategy = ioc.container.resolve_provider(ioc.StrategiesGroup.current_strategy)
        assert isinstance(strategy, BranchPrefixStrategy)
        assert strategy.name == "branch-prefix"


def test_container_resolves_conventional_commits_strategy_when_settings_strategy_is_cc() -> None:
    settings: typing.Final = _settings(strategy="conventional-commits")
    with ioc.container:
        ioc.container.set_context(Settings, settings)
        strategy = ioc.container.resolve_provider(ioc.StrategiesGroup.current_strategy)
        assert isinstance(strategy, ConventionalCommitsStrategy)
        assert strategy.name == "conventional-commits"


def test_named_strategy_factories_resolve_to_their_concrete_types_regardless_of_settings() -> None:
    settings: typing.Final = _settings(strategy="conventional-commits")
    with ioc.container:
        ioc.container.set_context(Settings, settings)
        bp = ioc.container.resolve_provider(ioc.StrategiesGroup.branch_prefix_strategy)
        cc = ioc.container.resolve_provider(ioc.StrategiesGroup.conventional_commits_strategy)
        assert isinstance(bp, BranchPrefixStrategy)
        assert isinstance(cc, ConventionalCommitsStrategy)
