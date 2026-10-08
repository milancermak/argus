# Runtime selection

Use one level of specialist delegation; keep orchestration in the current session. Do not choose a model or reasoning effort unless the user or project explicitly requires it.

## Named custom agents

When the spawn tool accepts a custom agent type/name, select the exact `argus-*` name as that type (`agent_type` in Codex CLI 0.153.4). A task label alone does not select a custom agent. Confirm selection from the tool result or runtime configuration; a similarly named ordinary subagent is not proof. Use a fresh child context: the CLI V1 full-history fork cannot override `agent_type`.

Installed definitions request `sandbox_mode = "read-only"`, but parent permission overrides may take precedence. Maintain the no-source-edit instruction in every assignment regardless of sandbox defaults.

Definitions live in `.codex/agents/` for a repository installation or `${CODEX_HOME:-$HOME/.codex}/agents/` for a personal installation. Repository agents require the project to be trusted in Codex; skills can be discovered even when its agents are ignored. The installer does not change trust. The skill's `agents/openai.yaml` supplies UI metadata; it does not register specialist agents. Discoverability may require a new session after installation.

## Prompt-based fallback

Some desktop collaboration tools expose task names but no custom-agent selector. In that case:

1. Read the requested specialist's installed TOML from the repository or personal location above. If reviewing this bundle without installing it, use its top-level `agents/` directory. Read the `developer_instructions` field and description, not every specialist.
2. Pass those instructions verbatim with the bounded assignment to an ordinary subagent. Start with a fresh context where supported; include necessary project instructions and source paths explicitly. Inherit runtime/model settings. TOML model, sandbox, tool, or skill configuration does not apply in this mode.
3. Record **prompt-based specialists; custom TOML configuration not loaded** in coverage. Preserve the same evidence and reporting contract.

If a definition is missing, report that specialty as unavailable. Do not fabricate a named-agent loading claim. If delegation is absent, the orchestrator may inspect remaining paths directly; report the reduced mode and mark material unfinished coverage incomplete.

## Optional tools

Git is needed to resolve commit ranges. Test runners, profilers, linters, browser/native UI tools, and documentation access depend on the target project; record missing evidence, without installing tools automatically. Select useful skills only if present.

`cccc` is optional for the simplicity reviewer. Before using it, inspect the installed version, `--help`, supported languages, and current [upstream documentation](https://github.com/moznion/cccc) and [changelog](https://github.com/moznion/cccc/blob/main/CHANGELOG.md). No wrapper or fixed JSON contract is bundled. For changes compare relevant functions before/after using scratch snapshots; for audits use scores to prioritize inspection. Record parse errors and unsupported files as missing metric coverage, not zero complexity. A score is not a finding; absence of the tool does not block a source review.
