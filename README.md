# Argus

![Argus: a centered computer monitor surrounded by falling green eyes scanning for code problems](assets/argus-readme.png)

Evidence-based code reviews for Codex. One skill coordinates five specialists:
correctness, simplicity, performance, architecture, and external contracts.
Findings are checked and reconciled into one report.

## Install

Requires Python 3.9+ and Codex with subagent support. Git is needed for commit ranges.

```sh
python3 install.py                         # personal installation
python3 install.py --project /path/to/repo # one repository
```

Personal files go to `~/.agents/skills/argus` and `.codex/agents`.
Project files go to `.agents/skills/argus` and `.codex/agents`; Codex must trust the
project to load its agents. Start a fresh session after installation.

Use `--update` after pulling changes, `--uninstall` to remove, or `--dry-run` to
preview. Edited, conflicting, and unrelated files are preserved. `--home PATH`
and `--codex-home PATH` support isolated installs. `--check` inspects CLI readiness.

## Use

```text
$argus review this repo
$argus review this repo for performance improvements
$argus review changes after abc123 through HEAD for performance regressions
$argus check naming consistency in the data layer
```

Focus and scope stay separate. Reviews leave application source unchanged unless
fixes are requested. Named agents inherit your model settings; runtimes without
named selection use an explicitly labelled prompt-based fallback. `cccc` is optional.

```sh
python3 -m unittest discover -s tests
```

See [verification](VERIFICATION.md) for tested runtimes and opt-in live checks.
Licensed under [MIT](LICENSE).
