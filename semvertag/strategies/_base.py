import typing

from semvertag._types import Bump, Commit


class BumpStrategy(typing.Protocol):
    name: str

    def decide(self, commit: Commit) -> Bump: ...
