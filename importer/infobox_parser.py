from __future__ import annotations


def _parse_array(value: str):
    items = []
    for line in value.strip().splitlines():
        text = line.strip().rstrip(",")
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1].strip()
        if text:
            items.append({"v": text})
    return items


def parse_infobox(raw: str | None) -> list[dict]:
    if not raw or not raw.strip():
        return []
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("|") or "=" not in line:
            i += 1
            continue
        key, value = line[1:].split("=", 1)
        key = key.strip()
        value = value.strip()
        if value == "{":
            block = []
            i += 1
            while i < len(lines) and lines[i].strip() != "}":
                block.append(lines[i])
                i += 1
            result.append({"key": key, "value": _parse_array("\n".join(block))})
        else:
            result.append({"key": key, "value": value})
        i += 1
    return result
