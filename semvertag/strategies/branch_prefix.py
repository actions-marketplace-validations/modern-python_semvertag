import dataclasses
import typing

import pydantic

from semvertag._types import Bump, Commit


_NonEmptyStr: typing.TypeAlias = typing.Annotated[str, pydantic.Field(min_length=1)]


class BranchPrefixConfig(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    minor: tuple[_NonEmptyStr, ...] = pydantic.Field(default=("feature/",), min_length=1)
    patch: tuple[_NonEmptyStr, ...] = pydantic.Field(default=("bugfix/", "hotfix/"), min_length=1)
    merge_mark_text: _NonEmptyStr = "Merge branch"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class BranchPrefixStrategy:
    name: typing.ClassVar[str] = "branch-prefix"
    config: BranchPrefixConfig

    def decide(self, commit: Commit) -> Bump:
        subject: typing.Final = commit.message.split("\n", 1)[0]
        if self.config.merge_mark_text not in subject:
            return Bump.NONE
        if any(prefix in subject for prefix in self.config.minor):
            return Bump.MINOR
        if any(prefix in subject for prefix in self.config.patch):
            return Bump.PATCH
        return Bump.NONE
