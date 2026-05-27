import pydantic


class BranchPrefixConfig(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    minor: tuple[str, ...] = ("feature/",)
    patch: tuple[str, ...] = ("bugfix/", "hotfix/")
    merge_mark_text: str = "Merge branch"
