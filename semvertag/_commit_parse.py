import typing


def subject_line(message: str) -> str:
    for line in message.splitlines():
        if line.strip():
            return line.rstrip()
    return ""


def body_lines(message: str) -> list[str]:
    lines: typing.Final = message.splitlines()
    subject_seen = False
    separator_seen = False
    collected: list[str] = []
    for line in lines:
        if not subject_seen:
            if line.strip():
                subject_seen = True
            continue
        if not separator_seen:
            if not line.strip():
                separator_seen = True
                continue
            collected.append(line.rstrip())
            continue
        if line.strip():
            collected.append(line.rstrip())
    return collected
