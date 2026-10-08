# Verification

Checked 2026-10-08 on macOS arm64. This is a local bundle; no global installation,
hooks, CI, remote hosting, or native plugin registration was performed.

## Contracts and versions

- Refreshed official [skill discovery](https://learn.chatgpt.com/docs/build-skills),
  [custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
  [configuration](https://learn.chatgpt.com/docs/config-file/config-reference),
  [environment variables](https://learn.chatgpt.com/docs/config-file/environment-variables),
  and [non-interactive execution](https://learn.chatgpt.com/docs/non-interactive-mode).
- Reviewed release notes for [0.153.4](https://github.com/openai/codex/releases/tag/rust-v0.153.4),
  [0.161.0](https://github.com/openai/codex/releases/tag/rust-v0.161.0), and
  [0.162.0-alpha.2](https://github.com/openai/codex/releases/tag/rust-v0.162.0-alpha.2).
- PATH CLI **0.153.4** accepted all five definitions through its actual app-server
  consumer. A malformed control emitted the expected configuration warning.
  Config fields passed the [versioned official schema](https://raw.githubusercontent.com/openai/codex/rust-v0.153.4/codex-rs/core/config.schema.json);
  standalone metadata was checked by the consumer, not that config-only schema.
- That older CLI rejected the configured `gpt-6.1-sol` before inference. Live tests
  used the already installed app-bundled CLI **0.162.0-alpha.2**, inheriting
  `gpt-6.1-sol` / `ultra`; no binary or user settings were changed.
- Actual discovery confirmed personal agents under `CODEX_HOME/agents`, repository
  agents only in trusted projects, and repository skills without project trust.
  `CODEX_HOME` does not isolate personal `HOME/.agents/skills` discovery.

## Results

- **24 installer tests** passed on Python **3.9.6** and **3.13.2**: isolated/project
  destinations, repeat installs, environment precedence, conflicts, ownership,
  updates/removal, unrelated configuration, symlinks, dry runs, and I/O rollback.
- Bundled skill-creator validator passed. UI YAML parsed; skill reference links
  resolved; all five standalone TOMLs parsed and passed official config validation.
- Each named specialist returned an unpredictable marker present only in its
  temporary installed instructions. Child traces confirmed exact `agent_role`,
  inherited model/effort, and effective read-only permissions in that run.
- Live fixtures exercised performance-only routing, correctness/performance
  reconciliation, clean code, naming consistency, and a blocked reviewer. Known
  stock and scaling problems were reported; clean code produced no findings;
  naming advice followed the project convention and considered callers. A blocked
  performance reviewer was disclosed and its area investigated by the orchestrator.
- A separate desktop-tool execution exercised prompt-based fallback: only the
  performance specialty, verbatim specialist instructions, explicit mode disclosure,
  and independent source/semantic/access-count checks.
- Application source remained unchanged. An independent evaluator checked reports
  against raw fixtures and available execution evidence; no finding quota or exact
  wording was required.

## Repeat live checks

The opt-in harness requires Python 3.11+, Git, and an existing file-backed Codex
login. It creates temporary repositories and `CODEX_HOME`, removes its temporary
auth copy afterward, and saves fixture/report/runtime/tool evidence outside this bundle.

```sh
python3.11 tests/live_review.py --case performance --output /path/to/new-evidence
```

Cases: `probe`, `performance`, `general`, `clean`, `naming`, `failure`. `--codex PATH`
selects an existing executable; `--timeout` bounds a run. Exit status checks process
success, source preservation, named routing, and probe markers; findings still need
assessment against the fixture. Tests do not provision authentication or a provider.

## Limits

Only macOS was exercised. Architecture and contracts had real loading probes;
their review quality was not evaluated against domain-specific integration fixtures.
Synthetic performance results are workload-specific. Effective permissions can be
overridden by a parent runtime; the TOML default alone is not an enforcement claim.
The host's existing personal skills were still discoverable during CLI tests.
Initial combined/failure exports omitted some specialist tool records, so their
exact specialist-only timing/test claims could not all be independently audited.
Repeated performance, clean, and naming checks retained auditable per-agent records.
`cccc` is optional guidance, with no installed-tool wrapper or tested output contract.
