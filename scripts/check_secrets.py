"""Fail if a file contains anything that looks like a secret.

Run in CI on n8n/workflow.json, so an export never ships an API key, token or
password. n8n keeps credentials in its own store and an export only references
them by id and name; this catches values pasted straight into nodes.

    python3 scripts/check_secrets.py n8n/workflow.json
    python3 scripts/check_secrets.py --self-test
"""

import json
import re
import sys
from pathlib import Path

TOKEN_PATTERNS = {
    "OpenAI/Anthropic-style key": r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}",
    "Google API key": r"\bAIza[0-9A-Za-z_-]{35}",
    "GitHub token": r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{20,})",
    "AWS access key": r"\bAKIA[0-9A-Z]{16}\b",
    "Slack token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "JWT": r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    "bearer token": r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}",
    "WordPress application password": r"\b(?:[A-Za-z0-9]{4} ){5}[A-Za-z0-9]{4}\b",
}
SENSITIVE_NAME = re.compile(
    r"(api[_-]?key|apikey|token|secret|password|passwd|authorization|x-api-key)", re.I
)
PLACEHOLDER = re.compile(r"^(|=.*|\{\{.*\}\}|<[^>]*>|YOUR_[A-Z_]+|changeme|\*+)$", re.S)


def _walk(node, path="$"):
    """Yield (path, key, value) for every string value, plus n8n name/value pairs."""
    if isinstance(node, dict):
        name, value = node.get("name"), node.get("value")
        if isinstance(name, str) and isinstance(value, str):
            yield f"{path}.value", name, value
        for k, v in node.items():
            if isinstance(v, str):
                yield f"{path}.{k}", k, v
            else:
                yield from _walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")


def find_secrets(text: str) -> list[str]:
    problems = [
        f"{label}: {m.group()[:12]}…"
        for label, pattern in TOKEN_PATTERNS.items()
        for m in re.finditer(pattern, text)
    ]
    try:
        data = json.loads(text)
    except ValueError:
        return problems
    for path, key, value in _walk(data):
        if SENSITIVE_NAME.search(key) and not PLACEHOLDER.match(value.strip()):
            problems.append(f"literal value for {key!r} at {path}")
    return problems


def self_test() -> None:
    bad = [
        '{"apiKey": "sk-proj-abcdefghijklmnopqrstuvwx"}',
        '{"headers": [{"name": "X-API-Key", "value": "hunter2hunter2"}]}',
        '{"parameters": {"password": "s3cret"}}',
        '{"text": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz012345"}',
        '{"note": "abcd efgh ijkl mnop qrst uvwx"}',
        '{"key": "AKIAABCDEFGHIJKLMNOP"}',
    ]
    good = [
        '{"credentials": {"openAiApi": {"id": "1", "name": "OpenAI account"}}}',
        '{"headers": [{"name": "X-API-Key", "value": "={{ $json.checkerApiKey }}"}]}',
        '{"parameters": {"apiKey": ""}}',
        '{"parameters": {"token": "<your token>"}}',
        '{"text": "Use the X-API-Key header"}',
    ]
    for sample in bad:
        assert find_secrets(sample), f"missed: {sample}"
    for sample in good:
        assert not find_secrets(sample), f"false positive: {sample} -> {find_secrets(sample)}"
    print(f"self-test ok ({len(bad)} bad, {len(good)} good samples)")


def main(paths: list[str]) -> int:
    failed = False
    for path in paths:
        for problem in find_secrets(Path(path).read_text(encoding="utf-8")):
            print(f"{path}: {problem}")
            failed = True
    if not failed:
        print(f"no secrets found in {', '.join(paths)}")
    return 1 if failed else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        self_test()
    else:
        sys.exit(main(sys.argv[1:]))
