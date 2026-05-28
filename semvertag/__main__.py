import dataclasses
import errno
import importlib.metadata
import typing

import pydantic
import typer

from semvertag import ioc
from semvertag._errors import ConfigError, SemvertagError
from semvertag._output import Output, build_json_output, build_rich_output
from semvertag._settings import Settings, apply_cli_overlay
from semvertag._use_case import SemvertagUseCase


_PACKAGE_NAME: typing.Final = "semvertag"


MAIN_APP: typing.Final = typer.Typer(
    name="semvertag",
    help=("Auto-tag GitLab/GitHub/Bitbucket repos with semantic version tags — one tool, two strategies."),
    invoke_without_command=True,
    no_args_is_help=False,
    add_completion=True,
)


def _version_callback(value: bool) -> None:
    if not value:
        return
    try:
        version = importlib.metadata.version(_PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        version = "0"
    typer.echo(version)
    raise typer.Exit


def _collect_overrides(  # noqa: PLR0913
    *,
    project_id: int | None,
    strategy: str | None,
    provider: str | None,
    token: str | None,
    default_branch: str | None,
    gitlab_endpoint: str | None,
    request_timeout: float | None,
    quiet: bool,
) -> dict[str, tuple[typing.Any, str]]:
    overrides: dict[str, tuple[typing.Any, str]] = {}
    if project_id is not None:
        overrides["project_id"] = (project_id, "--project-id")
    if strategy is not None:
        overrides["strategy"] = (strategy, "--strategy")
    if provider is not None:
        overrides["provider"] = (provider, "--provider")
    if token is not None:
        overrides["gitlab.token"] = (pydantic.SecretStr(token), "--token")
    if default_branch is not None:
        overrides["default_branch"] = (default_branch, "--default-branch")
    if gitlab_endpoint is not None:
        overrides["gitlab.endpoint"] = (gitlab_endpoint, "--gitlab-endpoint")
    if request_timeout is not None:
        overrides["request_timeout"] = (request_timeout, "--request-timeout")
    if quiet:
        overrides["quiet"] = (True, "--quiet")
    return overrides


def _config_error_from_validation(exc: pydantic.ValidationError) -> ConfigError:
    first: typing.Final = exc.errors()[0]
    loc: typing.Final = ".".join(str(part) for part in first.get("loc", ()))
    detail: typing.Final = first.get("msg", "invalid value")
    msg: typing.Final = f"Configuration error at '{loc}': {detail}. Check environment variables and command-line flags."
    return ConfigError(msg)


def _build_output_for_flags(*, quiet: bool, json_flag: bool) -> Output:
    if json_flag:
        return build_json_output(quiet=quiet)
    return build_rich_output(quiet=quiet)


@MAIN_APP.callback()
def _main_callback(  # noqa: PLR0913
    ctx: typer.Context,
    project_id: typing.Annotated[
        int | None,
        typer.Option("--project-id", help="GitLab project id (or set CI_PROJECT_ID)."),
    ] = None,
    strategy: typing.Annotated[
        str | None,
        typer.Option("--strategy", help="Bump strategy: branch-prefix | conventional-commits."),
    ] = None,
    provider: typing.Annotated[
        str | None,
        typer.Option("--provider", help="Provider: gitlab | github | bitbucket."),
    ] = None,
    token: typing.Annotated[
        str | None,
        typer.Option("--token", help="API token (overrides SEMVERTAG_TOKEN)."),
    ] = None,
    default_branch: typing.Annotated[
        str | None,
        typer.Option("--default-branch", help="Default branch name override."),
    ] = None,
    gitlab_endpoint: typing.Annotated[
        str | None,
        typer.Option("--gitlab-endpoint", help="GitLab API endpoint URL."),
    ] = None,
    request_timeout: typing.Annotated[
        float | None,
        typer.Option("--request-timeout", help="Per-request timeout in seconds (clamped to 10)."),
    ] = None,
    json_flag: typing.Annotated[
        bool,
        typer.Option("--json", help="Emit a JSON envelope on stdout instead of human-readable output."),
    ] = False,
    quiet: typing.Annotated[
        bool,
        typer.Option("--quiet", help="Suppress progress narrative; final result still emits."),
    ] = False,
    _version: typing.Annotated[
        bool | None,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version and exit."),
    ] = None,
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    output = _build_output_for_flags(quiet=quiet, json_flag=json_flag)

    try:
        settings = Settings()
        try:
            overrides = _collect_overrides(
                project_id=project_id,
                strategy=strategy,
                provider=provider,
                token=token,
                default_branch=default_branch,
                gitlab_endpoint=gitlab_endpoint,
                request_timeout=request_timeout,
                quiet=quiet,
            )
            settings = apply_cli_overlay(settings, overrides)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        output = _build_output_for_flags(quiet=settings.quiet, json_flag=json_flag)
        container = ioc.build_container(settings, json=json_flag)
        with container:
            use_case = container.resolve_provider(ioc.UseCasesGroup.semvertag_use_case)
            _run_with_output_override(use_case, output)
    except pydantic.ValidationError as exc:
        err = _config_error_from_validation(exc)
        output.error(str(err))
        raise typer.Exit(code=err.exit_code) from err
    except ImportError as exc:
        err = ConfigError(f"Required module unavailable: {exc}.")
        output.error(str(err))
        raise typer.Exit(code=err.exit_code) from err
    except SemvertagError as err:
        output.error(str(err))
        raise typer.Exit(code=err.exit_code) from err
    except BrokenPipeError as exc:
        raise typer.Exit(code=0) from exc
    except OSError as exc:
        if exc.errno == errno.EPIPE:
            raise typer.Exit(code=0) from exc
        raise


def _run_with_output_override(use_case: SemvertagUseCase, output: Output) -> None:
    dataclasses.replace(use_case, output=output).run()


def main() -> None:
    MAIN_APP()


if __name__ == "__main__":  # pragma: no cover
    main()
