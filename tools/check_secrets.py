"""Check tracked/staged files and reachable Git history without logging secrets."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT = re.compile(rb"(?m)^[ \t]*(?:export[ \t]+)?(?:STEAMDT_API_KEY|GITHUB_TOKEN|GH_TOKEN)[ \t]*=[ \t]*([^#\r\n]*)")
PATTERNS = [
    ("GitHub credential pattern", re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("AWS access-key pattern", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("Private key material", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]


def git(*args, input_bytes=None):
    result = subprocess.run(["git", *args], cwd=ROOT, input=input_bytes, capture_output=True)
    if result.returncode:
        raise RuntimeError("Git inspection failed; no file content printed")
    return result.stdout


def configured_secrets():
    values = {os.environ.get(name, "").strip() for name in ("STEAMDT_API_KEY", "GITHUB_TOKEN", "GH_TOKEN")}
    for path in (ROOT / ".env", ROOT / ".env.example", ROOT / "env.example"):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8-sig")
        for line in text.splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() in {"STEAMDT_API_KEY", "GITHUB_TOKEN", "GH_TOKEN"}:
                values.add(value.strip().strip('\"\''))
    return [value for value in values if len(value) >= 8]


def secret_encodings(secrets):
    encoded = set()
    for value in secrets:
        raw = value.encode("utf-8")
        encoded.update({raw, base64.b64encode(raw), base64.urlsafe_b64encode(raw), urllib.parse.quote(value, safe="").encode(), json.dumps(value, ensure_ascii=True)[1:-1].encode(), raw.hex().encode()})
    return encoded


def sensitive_path(path):
    name = Path(path).name.lower()
    return (
        (name.startswith(".env") and name != ".env.example")
        or name == "env.example"
        or name.endswith((".env", ".pem", ".key"))
        or (name.startswith("credentials") and name.endswith(".json"))
        or path.startswith("data/")
    )


def inspect_blob(content, encoded_secrets):
    findings = []
    if any(secret in content for secret in encoded_secrets):
        findings.append("Known local credential or encoded form")
    for match in ASSIGNMENT.finditer(content):
        if match.group(1).strip().strip(b"\"'").strip():
            findings.append("Nonempty credential assignment")
            break
    findings.extend(label for label, regex in PATTERNS if regex.search(content))
    return findings


def inspect_history(encoded_secrets):
    objects = git("rev-list", "--objects", "--all").splitlines()
    if not objects:
        return [], 0
    names = {}
    for line in objects:
        oid, _, name = line.partition(b" ")
        names[oid] = name.decode("utf-8", errors="replace") or "<historical object>"
    data = git("cat-file", "--batch", input_bytes=b"\n".join(names) + b"\n")
    offset, checked, findings = 0, 0, []
    while offset < len(data):
        end = data.index(b"\n", offset)
        header = data[offset:end].split()
        if len(header) != 3:
            raise RuntimeError("Unexpected Git object header")
        oid, kind, size = header
        size = int(size)
        content = data[end + 1:end + 1 + size]
        offset = end + 1 + size + 1
        if kind != b"blob":
            continue
        checked += 1
        path = names.get(oid, "<historical blob>")
        reasons = inspect_blob(content, encoded_secrets)
        if sensitive_path(path):
            reasons.append("Private artifact in Git history")
        if reasons:
            findings.append(("history:" + path, reasons))
    return findings, checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="Inspect bytes in the index")
    parser.add_argument("--history", action="store_true", help="Also inspect all reachable historical blobs")
    args = parser.parse_args()
    try:
        secrets = configured_secrets()
        encoded = secret_encodings(secrets)
        if args.staged:
            paths = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split(b"\0")
        else:
            paths = git("ls-files", "-z").split(b"\0")
        findings, checked = [], 0
        for raw_path in paths:
            if not raw_path:
                continue
            path = raw_path.decode("utf-8")
            content = git("show", ":" + path)
            checked += 1
            reasons = inspect_blob(content, encoded)
            if sensitive_path(path):
                reasons.append("Private artifact selected for publication")
            if reasons:
                findings.append((path, reasons))
        history_count = 0
        if args.history:
            history, history_count = inspect_history(encoded)
            findings.extend(history)
        if findings:
            print("Credential check BLOCKED:", file=sys.stderr)
            for path, reasons in findings:
                for value in secrets:
                    path = path.replace(value, "[REDACTED]")
                print("  " + path + ": " + ", ".join(reasons), file=sys.stderr)
            return 1
        if not checked:
            print("Credential check has no selected files; stage the release files first.", file=sys.stderr)
            return 1
        print(f"Credential check passed ({checked} selected files, {history_count} historical blobs); no values logged.")
        return 0
    except (RuntimeError, OSError, ValueError):
        print("Credential inspection failed; no credentials or file contents logged.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
