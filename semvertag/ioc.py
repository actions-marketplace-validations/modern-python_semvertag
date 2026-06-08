import typing

import httpware
import modern_di
from modern_di import Scope, providers

from semvertag._settings import Settings
from semvertag._use_case import SemvertagUseCase
from semvertag.providers._base import Provider
from semvertag.providers.github import GitHubProvider
from semvertag.providers.gitlab import GitLabProvider
from semvertag.strategies._base import BumpStrategy
from semvertag.strategies.branch_prefix import BranchPrefixStrategy
from semvertag.strategies.conventional_commits import ConventionalCommitsStrategy


_GITLAB_TOKEN_HEADER: typing.Final = "PRIVATE-TOKEN"
_GITHUB_ACCEPT: typing.Final = "application/vnd.github+json"
_GITHUB_API_VERSION: typing.Final = "2022-11-28"
_RETRY_STATUS_CODES: typing.Final = frozenset({408, 429, 500, 502, 503, 504})


def _build_gitlab_client(settings: Settings) -> httpware.Client:
    return httpware.Client(
        base_url=settings.gitlab.endpoint,
        timeout=settings.request_timeout,
        headers={_GITLAB_TOKEN_HEADER: settings.gitlab.token.get_secret_value()},
        middleware=[httpware.Retry(retry_status_codes=_RETRY_STATUS_CODES)],
    )


def _build_github_client(settings: Settings) -> httpware.Client:
    return httpware.Client(
        base_url=settings.github.endpoint,
        timeout=settings.request_timeout,
        headers={
            "Authorization": f"Bearer {settings.github.token.get_secret_value()}",
            "Accept": _GITHUB_ACCEPT,
            "X-GitHub-Api-Version": _GITHUB_API_VERSION,
        },
        middleware=[httpware.Retry(retry_status_codes=_RETRY_STATUS_CODES)],
    )


def _build_gitlab_provider(settings: Settings, client: httpware.Client) -> GitLabProvider:
    return GitLabProvider(
        config=settings.gitlab,
        project_id=settings.project_id,  # ty: ignore
        http=client,
    )


def _build_github_provider(settings: Settings, client: httpware.Client) -> GitHubProvider:
    return GitHubProvider(
        config=settings.github,
        repo=settings.repo,  # ty: ignore
        http=client,
    )


def _build_current_provider(
    settings: Settings,
    gitlab_provider: GitLabProvider,
    github_provider: GitHubProvider,
) -> Provider:
    if settings.provider == "github":
        return github_provider
    return gitlab_provider


def _build_branch_prefix_strategy(settings: Settings) -> BranchPrefixStrategy:
    return BranchPrefixStrategy(config=settings.branch_prefix)


def _build_conventional_commits_strategy(settings: Settings) -> ConventionalCommitsStrategy:
    return ConventionalCommitsStrategy(config=settings.conventional_commits)


def _build_current_strategy(settings: Settings) -> BumpStrategy:
    if settings.strategy == "conventional-commits":
        return _build_conventional_commits_strategy(settings)
    return _build_branch_prefix_strategy(settings)


def _close_gitlab_provider(provider: GitLabProvider) -> None:
    provider.http.close()


def _close_github_provider(provider: GitHubProvider) -> None:
    provider.http.close()


class SettingsGroup(modern_di.Group):
    settings = providers.ContextProvider(scope=Scope.APP, context_type=Settings)


class ProvidersGroup(modern_di.Group):
    gitlab_client = providers.Factory(scope=Scope.APP, creator=_build_gitlab_client, bound_type=None)
    gitlab_provider = providers.Factory(
        scope=Scope.APP,
        creator=_build_gitlab_provider,
        kwargs={"client": gitlab_client},
        cache_settings=providers.CacheSettings(finalizer=_close_gitlab_provider),
    )
    github_client = providers.Factory(scope=Scope.APP, creator=_build_github_client, bound_type=None)
    github_provider = providers.Factory(
        scope=Scope.APP,
        creator=_build_github_provider,
        kwargs={"client": github_client},
        cache_settings=providers.CacheSettings(finalizer=_close_github_provider),
    )
    current_provider = providers.Factory(
        scope=Scope.APP,
        creator=_build_current_provider,
        kwargs={"gitlab_provider": gitlab_provider, "github_provider": github_provider},
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
            "provider": ProvidersGroup.current_provider,
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
