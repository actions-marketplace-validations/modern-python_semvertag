import typing

import httpx2
import modern_di
from modern_di import Scope, providers

from semvertag._errors import ConfigError
from semvertag._output import JsonOutput, RichOutput, build_json_output, build_rich_output
from semvertag._settings import Settings
from semvertag._transport import RetryingTransport
from semvertag._use_case import SemvertagUseCase


if typing.TYPE_CHECKING:
    from semvertag.providers.gitlab import GitLabProvider
    from semvertag.strategies._base import BumpStrategy
    from semvertag.strategies.branch_prefix import BranchPrefixStrategy
    from semvertag.strategies.conventional_commits import ConventionalCommitsStrategy


def _build_rich_output(settings: Settings) -> RichOutput:
    return build_rich_output(quiet=settings.quiet)


def _build_json_output(settings: Settings) -> JsonOutput:
    return build_json_output(quiet=settings.quiet)


def _construct_gitlab_provider(
    settings: Settings,
    transport: httpx2.BaseTransport,
) -> "GitLabProvider":
    from semvertag.providers._http import HttpClient  # noqa: PLC0415
    from semvertag.providers.gitlab import GitLabProvider, _translate_status, gitlab_auth_headers  # noqa: PLC0415

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


def _build_gitlab_provider(settings: Settings) -> "GitLabProvider":
    return _construct_gitlab_provider(settings, transport=RetryingTransport())


def _build_branch_prefix_strategy(settings: Settings) -> "BranchPrefixStrategy":
    from semvertag.strategies.branch_prefix import BranchPrefixStrategy  # noqa: PLC0415

    return BranchPrefixStrategy(config=settings.branch_prefix)


def _build_conventional_commits_strategy(settings: Settings) -> "ConventionalCommitsStrategy":
    from semvertag.strategies.conventional_commits import ConventionalCommitsStrategy  # noqa: PLC0415

    return ConventionalCommitsStrategy(config=settings.conventional_commits)


def _build_current_strategy(settings: Settings) -> "BumpStrategy":
    if settings.strategy == "conventional-commits":
        return _build_conventional_commits_strategy(settings)
    return _build_branch_prefix_strategy(settings)


def _close_provider_client(provider: "GitLabProvider") -> None:
    provider.http.client.close()


class SettingsGroup(modern_di.Group):
    settings = providers.ContextProvider(scope=Scope.APP, context_type=Settings)


class OutputsGroup(modern_di.Group):
    rich_output = providers.Factory(
        scope=Scope.APP,
        creator=_build_rich_output,
        kwargs={"settings": SettingsGroup.settings},
        skip_creator_parsing=True,
        bound_type=None,
    )
    json_output = providers.Factory(
        scope=Scope.APP,
        creator=_build_json_output,
        kwargs={"settings": SettingsGroup.settings},
        skip_creator_parsing=True,
        bound_type=None,
    )


class ProvidersGroup(modern_di.Group):
    gitlab_provider = providers.Factory(
        scope=Scope.APP,
        creator=_build_gitlab_provider,
        kwargs={"settings": SettingsGroup.settings},
        skip_creator_parsing=True,
        bound_type=None,
        cache_settings=providers.CacheSettings(finalizer=_close_provider_client),
    )


class StrategiesGroup(modern_di.Group):
    branch_prefix_strategy = providers.Factory(
        scope=Scope.APP,
        creator=_build_branch_prefix_strategy,
        kwargs={"settings": SettingsGroup.settings},
        skip_creator_parsing=True,
        bound_type=None,
    )
    conventional_commits_strategy = providers.Factory(
        scope=Scope.APP,
        creator=_build_conventional_commits_strategy,
        kwargs={"settings": SettingsGroup.settings},
        skip_creator_parsing=True,
        bound_type=None,
    )
    current_strategy = providers.Factory(
        scope=Scope.APP,
        creator=_build_current_strategy,
        kwargs={"settings": SettingsGroup.settings},
        skip_creator_parsing=True,
        bound_type=None,
    )


class UseCasesGroup(modern_di.Group):
    semvertag_use_case = providers.Factory(
        scope=Scope.APP,
        creator=SemvertagUseCase,
        kwargs={
            "provider": ProvidersGroup.gitlab_provider,
            "strategy": StrategiesGroup.current_strategy,
            "output": OutputsGroup.rich_output,
        },
        skip_creator_parsing=True,
        bound_type=SemvertagUseCase,
    )


ALL_GROUPS: typing.Final[list[type[modern_di.Group]]] = [
    SettingsGroup,
    OutputsGroup,
    ProvidersGroup,
    StrategiesGroup,
    UseCasesGroup,
]


def build_container(
    settings: Settings,
    *,
    json: bool = False,
    inner_transport: httpx2.BaseTransport | None = None,
) -> modern_di.Container:
    if settings.provider != "gitlab":
        msg = f"Provider {settings.provider!r} not yet supported; v1.0 supports gitlab only."
        raise ConfigError(msg)
    container: typing.Final = modern_di.Container(
        groups=ALL_GROUPS,
        context={Settings: settings},
    )
    if inner_transport is not None:
        provider_instance: typing.Final = _construct_gitlab_provider(settings, inner_transport)
        container.override(ProvidersGroup.gitlab_provider, provider_instance)
    if json:
        json_instance: typing.Final = _build_json_output(settings)
        container.override(OutputsGroup.rich_output, json_instance)
    return container


__all__: typing.Final = (
    "ALL_GROUPS",
    "OutputsGroup",
    "ProvidersGroup",
    "SettingsGroup",
    "StrategiesGroup",
    "UseCasesGroup",
    "build_container",
)
