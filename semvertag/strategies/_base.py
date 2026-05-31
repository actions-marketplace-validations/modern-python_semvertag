import typing

from semvertag._types import Bump, Commit


class BumpStrategy(typing.Protocol):
    name: str
    no_bump_status: str
    no_bump_reason: str

    def decide(self, commit: Commit) -> Bump: ...
