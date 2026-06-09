import dataclasses
import typing

import semver

from semvertag._output import Output
from semvertag._types import Bump, RunResult, Tag
from semvertag.providers._base import Provider
from semvertag.strategies._base import BumpStrategy


_NO_TAGS_REASON: typing.Final = "No prior semver-conforming tags found; not seeding an initial tag in v1.0."
_ALREADY_TAGGED_REASON: typing.Final = "Latest commit already tagged."


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class SemvertagUseCase:
    provider: Provider
    strategy: BumpStrategy

    def __call__(self, *, output: Output, dry_run: bool = False) -> RunResult:
        output.progress(f"Detected strategy: {self.strategy.name}")
        output.progress("Fetching latest commit on default branch...")
        commit: typing.Final = self.provider.get_latest_commit_on_default_branch()

        output.progress("Fetching tag history...")
        tags: typing.Final = self.provider.list_tags()
        latest_semver_tag: typing.Final = _pick_latest_semver_tag(tags)

        if latest_semver_tag is None:
            return self._emit(
                output=output,
                bump=Bump.NONE,
                status="no_tags",
                tag=None,
                commit=commit.sha,
                reason=_NO_TAGS_REASON,
            )

        if latest_semver_tag.commit_sha == commit.sha:
            return self._emit(
                output=output,
                bump=Bump.NONE,
                status="already_tagged",
                tag=latest_semver_tag.name,
                commit=commit.sha,
                reason=_ALREADY_TAGGED_REASON,
            )

        output.progress("Computing bump...")
        bump: typing.Final = self.strategy.decide(commit)
        if bump is Bump.NONE:
            return self._emit(
                output=output,
                bump=Bump.NONE,
                status=self.strategy.no_bump_status,
                tag=None,
                commit=commit.sha,
                reason=self.strategy.no_bump_reason,
            )

        new_version: typing.Final = _compute_new_version(latest_semver_tag, bump)
        if dry_run:
            return self._emit(
                output=output,
                bump=bump,
                status="dry_run",
                tag=new_version,
                commit=commit.sha,
                reason=None,
            )

        output.progress(f"Creating tag {new_version}...")
        self.provider.create_tag(name=new_version, commit_sha=commit.sha)
        return self._emit(
            output=output,
            bump=bump,
            status="created",
            tag=new_version,
            commit=commit.sha,
            reason=None,
        )

    def _emit(  # noqa: PLR0913
        self,
        *,
        output: Output,
        bump: Bump,
        status: str,
        tag: str | None,
        commit: str | None,
        reason: str | None,
    ) -> RunResult:
        result: typing.Final = RunResult(
            strategy=self.strategy.name,
            bump=bump.value,
            status=status,
            tag=tag,
            commit=commit,
            reason=reason,
        )
        output.emit(result)
        return result


def _pick_latest_semver_tag(tags: list[Tag]) -> Tag | None:
    parsed: typing.Final = [(version, tag) for tag, version in _parse_semver_tags(tags)]
    if not parsed:
        return None
    parsed.sort(key=lambda item: item[0])
    return parsed[-1][1]


def _parse_semver_tags(tags: list[Tag]) -> typing.Iterator[tuple[Tag, semver.Version]]:
    for tag in tags:
        version = _try_parse_semver(tag.name)
        if version is not None:
            yield tag, version


def _try_parse_semver(name: str) -> semver.Version | None:
    try:
        return semver.Version.parse(name)
    except ValueError:
        return None


_BUMP_FUNCTIONS: typing.Final[dict[Bump, typing.Callable[[semver.Version], semver.Version]]] = {
    Bump.MAJOR: semver.Version.bump_major,
    Bump.MINOR: semver.Version.bump_minor,
    Bump.PATCH: semver.Version.bump_patch,
}


def _compute_new_version(last_tag: Tag, bump: Bump) -> str:
    version: typing.Final = semver.Version.parse(last_tag.name)
    return str(_BUMP_FUNCTIONS[bump](version))
