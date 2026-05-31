import typing

import httpx2
import modern_di
from modern_di import Scope, providers

from semvertag._errors import ConfigError
from semvertag._settings import Settings
from semvertag._transport import RetryingTransport
from semvertag._use_case import SemvertagUseCase
from semvertag.providers._http import HttpClient
from semvertag.providers.gitlab import GitLabProvider, _translate_status, gitlab_auth_headers
from semvertag.strategies._base import BumpStrategy
from semvertag.strategies.branch_prefix import BranchPrefixStrategy
from semvertag.strategies.conventional_commits import ConventionalCommitsStrategy


def _build_gitlab_provider(settings: Settings, transport: httpx2.BaseTransport) -> GitLabProvider:
    if settings.project_id is None:
        msg = "Project id missing. Set CI_PROJECT_ID or pass --project-id."
        raise ConfigError(msg)
    project_id: typing.Final = settings.project_id
    client: typing.Final = httpx2.Client(
        transport=transport,
        base_url=settings.gitlab.endpoint,
        timeout=settings.request_timeout,
    )
    http: typing.Final = HttpClient(
        client=client,
        auth_headers=lambda: gitlab_auth_headers(settings.gitlab.token),
        status_translator=lambda status: _translate_status(status, project_id),
    )
    return GitLabProvider(
        config=settings.gitlab,
        project_id=project_id,
        http=http,
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
    provider.http.client.close()


class SettingsGroup(modern_di.Group):
    settings = providers.ContextProvider(scope=Scope.APP, context_type=Settings)


class TransportsGroup(modern_di.Group):
    transport = providers.Factory(scope=Scope.APP, creator=RetryingTransport)


class ProvidersGroup(modern_di.Group):
    gitlab_provider = providers.Factory(
        scope=Scope.APP,
        creator=_build_gitlab_provider,
        kwargs={"transport": TransportsGroup.transport},
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
    TransportsGroup,
    ProvidersGroup,
    StrategiesGroup,
    UseCasesGroup,
]


container: typing.Final = modern_di.Container(groups=ALL_GROUPS)
