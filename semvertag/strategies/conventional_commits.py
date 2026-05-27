import pydantic


class ConventionalCommitsConfig(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True)

    minor_types: tuple[str, ...] = ("feat",)
    patch_types: tuple[str, ...] = ("fix", "perf")
