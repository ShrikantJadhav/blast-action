# Blast Guardrail Scan

A GitHub Action that runs [`blast`](https://github.com/ShrikantJadhav/blast) on a pull request and turns its findings into inline annotations plus a job-summary report. No model, no API key, no network calls from the scanner itself.

Blast answers one narrow question: **did this change earn its green, or did it weaken the checks?** It flags skipped tests, suppressed errors, committed secrets, new `exec`/network capability, risky path changes, and large or testless diffs.

## Quick start

```yaml
name: Blast guardrails

on:
  pull_request:

permissions:
  contents: read

jobs:
  blast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: ShrikantJadhav/blast-action@v1
        with:
          base: origin/${{ github.event.pull_request.base.ref }}
```

`fetch-depth: 0` matters: Blast needs the base ref to build the diff.

To make it a real **gate**, go to **Settings → Rules → Branch protection / Rulesets** and mark the `Blast guardrails / blast` check as required. Without that, the check is advisory even when it fails.

## Inputs

| Input | Default | Description |
|---|---|---|
| `base` | `origin/main` | Git ref to diff against. |
| `policy` | `""` | Path to a `blast.toml` policy file. |
| `max-risk` | `""` | Override `max_risk` from policy (default 70). |
| `max-files` | `""` | Override `max_files` from policy (default 40). |
| `fail-on` | `""` | Override `fail_on` severity: `info`, `low`, `medium`, `high`, `critical`. |
| `require-tests` | `""` | Override `require_tests` with `true` or `false`. Empty uses the policy/default. |
| `deny` | `""` | Comma- or newline-separated path globs appended to the policy deny list. |
| `version` | `latest` | Go version query for the Blast CLI: `latest`, `v0.1.0`, or a commit. |
| `advisory` | `false` | Emit annotations and summary but never fail the job. |

### Advisory / shadow mode

Start non-blocking while you tune policy:

```yaml
- uses: ShrikantJadhav/blast-action@v1
  with:
    base: origin/${{ github.event.pull_request.base.ref }}
    advisory: "true"
```

The job stays green, but findings still appear as annotations and in the summary. Flip `advisory` to `false` once noise is acceptable.

## Outputs

| Output | Example | Description |
|---|---|---|
| `score` | `100` | Risk score, 0–100. |
| `verdict` | `SEVERE` | `LOW`, `MODERATE`, `ELEVATED`, or `SEVERE`. |
| `findings` | `7` | Number of findings. |
| `policy` | `fail` | `pass` or `fail`. |

Use them in a later step:

```yaml
- uses: ShrikantJadhav/blast-action@v1
  id: blast
  with:
    base: origin/${{ github.event.pull_request.base.ref }}

- run: echo "Blast said ${{ steps.blast.outputs.verdict }} (${{ steps.blast.outputs.findings }} findings)"
```

## Policy example

Commit `blast.toml` in the target repo and point the action at it:

```toml
max_risk = 70
max_files = 40
fail_on = "high"
require_tests = true

deny = [
  "infra/**",
  ".github/workflows/**",
  "**/*.pem",
  "**/.env",
]
```

```yaml
- uses: ShrikantJadhav/blast-action@v1
  with:
    policy: blast.toml
    base: origin/${{ github.event.pull_request.base.ref }}
```

For team-wide rollout, publish the policy in a shared repo and download it before the scan.

## What a failing check looks like

Annotations land on the exact changed line:

```text
internal/api/session_test.go:20  CRITICAL · test-integrity
test skipped instead of fixed: t.Skip("flaky in CI, revisit later")
```

The step summary shows the score, severity counts, and every finding in a collapsible section.

## Local smoke test

The annotation script is plain Python 3 with no dependencies:

```sh
blast scan --json --patch ../blast/examples/sketchy.patch > /tmp/blast-scan.json
GITHUB_STEP_SUMMARY=/tmp/summary.md \
GITHUB_OUTPUT=/tmp/output.txt \
python3 scripts/annotate.py /tmp/blast-scan.json
```

## Relationship to Samiksha

This action is the deterministic floor: cheap, repeatable, and impossible to hallucinate away. [`samiksha-action`](https://github.com/ShrikantJadhav/samiksha-action) adds an optional evidence-backed agent review on top of the same diff.

## License

MIT.
