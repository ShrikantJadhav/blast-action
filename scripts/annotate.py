#!/usr/bin/env python3
"""Turn `blast scan --json` output into GitHub annotations and a step summary."""

from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path

LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "notice",
    "info": "notice",
}
ORDER = ("critical", "high", "medium", "low", "info")


def esc_property(value: object) -> str:
    text = str(value)
    return (
        text.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
        .replace(":", "%3A")
        .replace(",", "%2C")
    )


def esc_data(value: object) -> str:
    text = str(value)
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def annotation(level: str, message: str, *, path: str = "", line: int = 0, title: str = "") -> None:
    properties = []
    if path:
        properties.append("file=" + esc_property(path))
    if line and line > 0:
        properties.append("line=" + esc_property(line))
    if title:
        properties.append("title=" + esc_property(title))
    prefix = "::" + level
    if properties:
        prefix += " " + ",".join(properties)
    print(prefix + "::" + esc_data(message))


def set_output(name: str, value: object) -> None:
    path = os.getenv("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")


def append_summary(text: str) -> None:
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text.rstrip() + "\n\n")


def no_changes(raw: str) -> bool:
    return "no changes detected" in raw.lower()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: annotate.py <blast-scan.json>", file=sys.stderr)
        return 2

    raw = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        if no_changes(raw):
            annotation("notice", "Blast: no changes detected")
            set_output("score", 0)
            set_output("verdict", "none")
            set_output("findings", 0)
            append_summary("### Blast guardrail scan\n\n_No changes detected._")
            return 0
        print("::error::blast did not return JSON")
        print(raw[:2000], file=sys.stderr)
        return 2

    findings = result.get("findings") or []
    stats = result.get("stats") or {}
    score = int(result.get("score", 0))
    verdict = str(result.get("verdict", "unknown")).upper()

    counts = {name: 0 for name in ORDER}
    for finding in findings:
        severity = str(finding.get("severity", "info")).lower()
        if severity in counts:
            counts[severity] += 1
        level = LEVEL.get(severity, "notice")
        rule = str(finding.get("rule") or "finding")
        message = str(finding.get("message") or rule)
        annotation(
            level,
            message,
            path=str(finding.get("path") or ""),
            line=int(finding.get("line") or 0),
            title=f"{rule} · {severity}",
        )

    if not findings:
        annotation("notice", "Blast found no guardrail findings")

    set_output("score", score)
    set_output("verdict", verdict)
    set_output("findings", len(findings))

    severity_line = " · ".join(f"{counts[name]} {name}" for name in ORDER if counts[name])
    lines = [
        "### Blast guardrail scan",
        "",
        f"- Verdict: **{html.escape(verdict)}**",
        f"- Risk score: **{score}/100**",
        f"- Diff: **{int(stats.get('files', 0))}** files "
        f"(+{int(stats.get('added', 0))}/−{int(stats.get('removed', 0))})",
        f"- Findings: **{len(findings)}**"
        + (f" — {html.escape(severity_line)}" if severity_line else ""),
        "",
        "<details><summary>Findings</summary>",
        "",
    ]
    if findings:
        for finding in findings:
            severity = str(finding.get("severity", "info")).upper()
            rule = html.escape(str(finding.get("rule") or "finding"))
            path = html.escape(str(finding.get("path") or "diff"))
            line = int(finding.get("line") or 0)
            where = f"{path}:{line}" if line else path
            message = html.escape(str(finding.get("message") or ""))
            lines.append(f"- **{severity}** `{rule}` — `{where}` — {message}")
    else:
        lines.append("_None_.")
    lines += ["", "</details>"]
    append_summary("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
