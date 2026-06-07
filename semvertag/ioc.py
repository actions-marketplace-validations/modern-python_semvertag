import typing

import httpware
import modern_di
from modern_di import Scope, providers

from semvertag._errors import ConfigError
from semvertag._settings import Settings
from semvertag._use_case import SemvertagUseCase
from semvertag.providers.gitlab import GitLabProvider
from semvertag.strategies._base import BumpStrategy
from semvertag.strategies.branch_prefix import BranchPrefixStrategy
from semvertag.strategies.conventional_commits import ConventionalCommitsStrategy


_TOKEN_HEADER: typing.Final = "PRIVATE-TOKEN"
_RETRY_STATUS_CODES: typing.Final = frozenset({408, 429, 500, 502, 503, 504})


def _build_gitlab_client(settings: Settings) -> httpware.Client:
    return httpware.Client(
        base_url=settings.gitlab.endpoint,
        timeout=settings.request_timeout,
        headers={_TOKEN_HEADER: settings.gitlab.token.get_secret_value()},
        middleware=[httpware.Retry(retry_status_codes=_RETRY_STATUS_CODES)],
    )


def _build_gitlab_provider(settings: Settings, client: httpware.Client) -> GitLabProvider:
    if settings.project_id is None:
        msg = "Project id missing. Set CI_PROJECT_ID or pass --project-id."
        raise ConfigError(msg)
    return GitLabProvider(
        config=settings.gitlab,
        project_id=settings.project_id,
        http=client,
    )


def _build_branch_prefix_strategy(settings: Settings) -> BranchPrefixStrategy:
    return BranchPrefixStrategy(config=settings.branch_prefix)


def _build_conventional_commits_strategy(settings: Settings) -> ConventionalCommitsStrategy:
    return ConventionalCommitsStrategy(config=settings.conventional_commits)


def _build_current_strategy(settings: Settings) -> BumpStrategy:
    if settings.strategy == "conventional-commits":
        return _build_conventional_commits_strategy(settings)
    return _build_branch_prefix_strategy(settings)


def _close_provider_client(provider: GitLabProvider) -> None:
    provider.http.close()


class SettingsGroup(modern_di.Group):
    settings = providers.ContextProvider(scope=Scope.APP, context_type=Settings)


class ProvidersGroup(modern_di.Group):
    gitlab_client = providers.Factory(scope=Scope.APP, creator=_build_gitlab_client)
    gitlab_provider = providers.Factory(
        scope=Scope.APP,
        creator=_build_gitlab_provider,
        kwargs={"client": gitlab_client},
        cache_settings=providers.CacheSettings(finalizer=_close_provider_client),
    )


class StrategiesGroup(modern_di.Group):
    branch_prefix_strategy = providers.Factory(scope=Scope.APP, creator=_build_branch_prefix_strategy)
    conventional_commits_strategy = providers.Factory(scope=Scope.APP, creator=_build_conventional_commits_strategy)
    current_strategy = providers.Factory(scope=Scope.APP, creator=_build_current_strategy)


class UseCasesGroup(modern_di.Group):
    semvertag_use_case = providers.Factory(
        scope=Scope.APP,
        creator=SemvertagUseCase,
        kwargs={
            "provider": ProvidersGroup.gitlab_provider,
            "strategy": StrategiesGroup.current_strategy,
        },
    )


ALL_GROUPS: typing.Final[list[type[modern_di.Group]]] = [
    SettingsGroup,
    ProvidersGroup,
    StrategiesGroup,
    UseCasesGroup,
]


container: typing.Final = modern_di.Container(groups=ALL_GROUPS)
