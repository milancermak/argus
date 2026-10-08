---
name: argus
description: Coordinate evidence-based code reviews and repository audits with specialist agents for correctness, simplicity, performance, architecture, and external contracts. Use for general or explicitly focused reviews, including commit ranges and working changes.
---

# Argus

Own the scope, coverage, evidence, and final report. Delegate bounded investigations to specialist agents; check their conclusions and reconcile disagreements. Review without editing application source unless fixes are requested. Put scratch evidence in a separate temporary destination.

## Scope and focus

Treat scope and focus independently. A repository audit examines existing code and opportunities; a change review identifies introduced or worsened issues. Honor an explicit focus: performance-only requests launch only performance reviewers. Existing unrelated defects are outside a change review unless the user expands its scope.

For changes, resolve exact base/head SHAs, starting-commit inclusion, and dirty state. "After abc123 through HEAD" means `abc123..HEAD`, excluding abc123. "Including abc123" starts at its first parent; account for root and merge commits explicitly. Unqualified "review changes" means staged, unstaged, and relevant untracked changes; record what is included. An explicit committed range excludes working changes unless requested. Never reset, stash, or switch the user's checkout to obtain evidence. Clarify only ambiguity that would materially alter scope.

For an audit, map relevant components, entry points, and execution paths. Prioritize the requested concern and disclose sampling. Inspect surrounding source, callers, consumers, and tests, even when they lie outside the diff.

## Reviewers

| Agent | Responsibility |
| --- | --- |
| `argus-correctness` | Behavior, state, concurrency, cancellation, errors, recovery, cleanup |
| `argus-simplicity` | Complexity, duplication, indirection, naming/terminology consistency, code removal |
| `argus-performance` | Repeated work, blocking, allocations, resources, scaling |
| `argus-architecture` | Responsibilities, dependencies, ownership, boundaries |
| `argus-contracts` | APIs, SDKs, protocols, versions, lifecycle, consumer compatibility |

For a general review select specialties from the affected behavior, not a mandatory five-agent checklist. Cover relevant security and UI interaction risks through suitable reviewers or direct investigation; disclose a material gap. Every specialist owns relevant tests and missing scenarios. Load other available skills selectively and respect project decisions; generic advice does not override them.

Use the installed named custom agents when the runtime can select them. Read [runtime.md](references/runtime.md) before first delegation to choose the supported mode. If named selection is unavailable, use the documented prompt-based specialist fallback and label it; never imply TOML settings were loaded. If no delegation works, disclose that limitation and investigate directly, marking material unmet coverage incomplete.

## Delegate and track

An Argus invocation calls for delegation. Give each reviewer the original request, exact scope/focus, a bounded component or question, project instructions, source access, scratch destination, and this result contract:

- Findings: category (defect, maintainability suggestion, or performance opportunity), impact, exact source location, trigger/scenario, concrete consequence, evidence, smallest reasonable improvement, and relevant test or missing scenario.
- Performance evidence: measured or inferred; include workload/method when measured and validation needed when inferred.
- Coverage: inspected paths, checks actually run and outcomes, unreviewed paths, failed checks, and limitations. No findings is valid.

Supply raw evidence without suggesting a preferred conclusion. Use separate contexts where supported. Split a large specialty by component; retain an owner for cross-component paths. Schedule within actual concurrency limits and release completed slots. Track every assignment to completion or a stated failure; do not silently discard missing reviewers. Retry a failed assignment once with a bounded correction when useful, otherwise cover it directly or mark the review incomplete. Specialists report to the orchestrator and do not spawn further reviewers.

## Verify and reconcile

Check material findings against source, callers, consumers, and tests. Remove duplicates and comments already covered adequately by linters or formatters. Require a concrete consequence; smells, complexity scores, and generic best practices alone are not findings. Attribute change-review findings to an introduced or worsened path.

Resolve conflicting recommendations with targeted evidence or follow-up. Weigh complexity, performance, and compatibility together; present the smallest justified improvement and any relevant tradeoff. Keep demonstrated defects distinct from suggestions and hypotheses. Label inferred performance claims; never invent speedups or call unexecuted checks passed. Return no findings when supported.

## Report

Lead with actionable findings ordered by impact. Each needs a location, affected scenario, consequence, evidence, and improvement. Put maintainability suggestions and performance opportunities separately from defects, with the validation still needed. Keep the report proportionate to the findings.

Finish with concise coverage: exact scope and dirty-state inclusion, specialties and actual delegation mode, verification performed, sampling, failures, and limitations. Mark material missing coverage **incomplete**. Do not claim all defects were found.
