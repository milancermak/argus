#!/usr/bin/env python3
"""Opt-in real Codex reviews; uses existing login and writes only temporary fixtures.

Requires Python 3.11+. No expected findings are passed to the reviewer. Reports
and event traces are saved separately for independent assessment.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import uuid


BUNDLE = Path(__file__).resolve().parents[1]
SPECIALTIES = ("correctness", "simplicity", "performance", "architecture", "contracts")
BASE_SOURCE = '''"""In-memory inventory and user lookups."""


def reserve(stock, lines):
    totals = {}
    for sku, quantity in lines:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        totals[sku] = totals.get(sku, 0) + quantity
    for sku, quantity in totals.items():
        if stock[sku] < quantity:
            raise ValueError("insufficient stock")
    for sku, quantity in totals.items():
        stock[sku] -= quantity


def find_users(user_ids, users):
    first_by_id = {}
    for user in users:
        first_by_id.setdefault(user["id"], user)
    return [first_by_id[user_id] for user_id in user_ids]
'''
HEAD_SOURCE = '''"""In-memory inventory and user lookups."""


def reserve(stock, lines):
    for sku, quantity in lines:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if stock[sku] < quantity:
            raise ValueError("insufficient stock")
    for sku, quantity in lines:
        stock[sku] -= quantity


def find_users(user_ids, users):
    result = []
    for user_id in user_ids:
        for user in users:
            if user["id"] == user_id:
                result.append(user)
                break
        else:
            raise KeyError(user_id)
    return result
'''
CLEAN_SOURCE = '''"""Normalize one required stock identifier."""


def normalize_sku(value):
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("stock identifier is required")
    return normalized
'''
NAMING_SOURCE = '''"""All customer accessors read the same in-memory records."""


def get_customer(records, customer_id):
    return records[customer_id]


def get_customer_email(records, customer_id):
    return records[customer_id]["email"]


def load_customer_name(records, customer_id):
    return records[customer_id]["name"]
'''
TEST_SOURCE = '''import unittest
from inventory import find_users, reserve
from clean import normalize_sku


class InventoryTests(unittest.TestCase):
    def test_single_reservation(self):
        stock = {"book": 5}
        reserve(stock, [("book", 2)])
        self.assertEqual(stock, {"book": 3})

    def test_lookup_preserves_first_match_and_request_order(self):
        users = [{"id": 1, "name": "first"}, {"id": 1, "name": "later"}, {"id": 2}]
        self.assertEqual(find_users([2, 1, 1], users), [users[2], users[0], users[0]])

    def test_unknown_user(self):
        with self.assertRaises(KeyError):
            find_users([3], [{"id": 1}])

    def test_normalize(self):
        self.assertEqual(normalize_sku("  b-2  "), "B-2")
        with self.assertRaises(ValueError):
            normalize_sku("  ")
'''


def run(command, **kwargs):
    return subprocess.run(command, check=True, text=True, capture_output=True, **kwargs)


def fixture(root):
    repo = root / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "main", str(repo)])
    (repo / "AGENTS.md").write_text(
        "Review scope is explicit. Do not change source. Customer accessor names use get_. "
        "Each stock line has a positive quantity; a SKU may occur more than once. "
        "User IDs and user records may repeat; first matching record wins. "
        "Tests use Python unittest. Performance workload: 10,000 requested IDs and "
        "100,000 user records. No external APIs are used.\n", encoding="utf-8")
    for name, source in (("inventory.py", BASE_SOURCE), ("clean.py", CLEAN_SOURCE),
                         ("customers.py", NAMING_SOURCE), ("test_inventory.py", TEST_SOURCE)):
        (repo / name).write_text(source, encoding="utf-8")
    git = ["git", "-C", str(repo)]
    commit = git + ["-c", "user.name=Argus fixture", "-c", "user.email=fixture@example.invalid",
                    "-c", "core.hooksPath=/dev/null", "commit", "-m"]
    run(git + ["add", "."])
    run(commit + ["Baseline"])
    base = run(git + ["rev-parse", "HEAD"]).stdout.strip()
    (repo / "inventory.py").write_text(HEAD_SOURCE, encoding="utf-8")
    run(git + ["add", "inventory.py"])
    run(commit + ["Change reservation and lookup"])
    head = run(git + ["rev-parse", "HEAD"]).stdout.strip()
    run([sys.executable, str(BUNDLE / "install.py"), "--project", str(repo)])
    # Test-only untracked dirt proves an explicit committed review excludes it.
    (repo / "local-notes.txt").write_text("Uncommitted fixture note.\n", encoding="utf-8")
    return repo, base, head


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True,
                        choices=("probe", "performance", "general", "clean", "failure", "naming"))
    parser.add_argument("--output", required=True, type=Path,
                        help="empty evidence directory outside the bundle")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--codex", default="codex", help="CLI executable or absolute path")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == BUNDLE or BUNDLE in output.parents or output.exists():
        parser.error("--output must be a new directory outside the bundle")
    executable = shutil.which(args.codex)
    if executable is None:
        parser.error("codex must be on PATH and already authenticated")
    original_codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    auth = original_codex_home / "auth.json"
    if not auth.is_file():
        parser.error("this harness requires an existing file-backed Codex login")
    output.mkdir(parents=True)
    temporary_parent = Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix="argus-live-", dir=temporary_parent) as temporary:
        root = Path(temporary)
        repo, base, head = fixture(root)
        codex_home = root / "codex-home"
        codex_home.mkdir(mode=0o700)
        shutil.copyfile(auth, codex_home / "auth.json")
        (codex_home / "auth.json").chmod(0o600)
        config = {}
        if (original_codex_home / "config.toml").is_file():
            config = tomllib.loads((original_codex_home / "config.toml").read_text())
        config_lines = [f"{key} = {json.dumps(config[key])}" for key in
                        ("model", "model_provider", "model_reasoning_effort") if key in config]
        if config.get("model_provider", "openai") != "openai":
            parser.error("custom model providers require a separately configured environment")
        config_lines += ["[agents]", "max_threads = 3", f"[projects.{json.dumps(str(repo))}]",
                         'trust_level = "trusted"']
        (codex_home / "config.toml").write_text("\n".join(config_lines) + "\n")
        markers = {}
        if args.case == "probe":
            for specialty in SPECIALTIES:
                path = repo / ".codex" / "agents" / f"argus-{specialty}.toml"
                marker = "argus_loaded_" + uuid.uuid4().hex
                markers[specialty] = marker
                text = path.read_text()
                # Marker exists only in the installed definition, never in its assignment.
                text = text.replace('developer_instructions = """',
                                    'developer_instructions = """\n'
                                    'For a configuration probe, reply only with this marker: '
                                    + marker + '\n', 1)
                path.write_text(text)
            request = ("Use the five named custom Argus agents, one for each specialty, in fresh "
                       "contexts, within concurrency limits. Assign each only 'configuration probe'. "
                       "Wait for each result and close completed agents. Do not read their TOMLs "
                       "or supply marker text. Report their five verbatim responses and selection "
                       "mode. This is a loading probe, not a code review.")
        else:
            requests = {
                "performance": f"$argus review changes after {base} through {head} for performance regressions",
                "general": f"$argus review changes after {base} through {head} for correctness and performance",
                "clean": "$argus audit only clean.py for correctness and performance",
                "naming": "$argus audit customers.py for naming consistency",
                "failure": "$argus audit inventory.py for correctness and performance",
            }
            request = requests[args.case]
            if args.case == "failure":
                path = repo / ".codex" / "agents" / "argus-performance.toml"
                path.write_text('name = "argus-performance"\n'
                                'description = "Performance fixture reviewer"\n'
                                'sandbox_mode = "read-only"\n'
                                'developer_instructions = """Performance source evidence is '
                                'unavailable in this test. Return a blocked review with no findings, '
                                'no inspected files and no executed checks; do not investigate."""\n')
            request += ("\nUse the installed skill; make no source changes. Keep the final report "
                        "concise, with findings, evidence, exact scope/dirty-state inclusion, "
                        "specialties/mode, checks run, and limitations. Do not launch specialties "
                        "outside the requested focus.")
        (output / "request.txt").write_text(request + "\n")
        before = {path.name: path.read_bytes() for path in repo.glob("*.py")}
        environment = dict(os.environ, CODEX_HOME=str(codex_home))
        command = [executable, "exec", "--json", "--sandbox", "read-only",
                   "--cd", str(repo), "--output-last-message", str(output / "report.txt"), "-"]
        print(f"Running {args.case}: {run([executable, '--version']).stdout.strip()}", flush=True)
        try:
            with (output / "events.jsonl").open("w") as events, (output / "stderr.txt").open("w") as errors:
                result = subprocess.run(command, input=request, text=True, stdout=events,
                                        stderr=errors, env=environment, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print(f"Timed out; evidence preserved at {output}", file=sys.stderr)
            return 1
        after = {path.name: path.read_bytes() for path in repo.glob("*.py")}
        metadata = {"case": args.case, "base": base, "head": head,
                    "exit_code": result.returncode, "source_unchanged": before == after,
                    "markers": markers, "model": config.get("model"),
                    "reasoning_effort": config.get("model_reasoning_effort")}
        # Preserve applied runtime fields, not raw sessions, credentials, or config.
        sessions = []
        trace_directory = output / "tool-traces"
        trace_directory.mkdir()
        for path in sorted(codex_home.glob("sessions/**/*.jsonl")):
            summary = {}
            tool_items = []
            for line in path.read_text().splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = event.get("payload", {})
                if event.get("type") == "session_meta":
                    for key in ("id", "agent_role", "source", "cli_version"):
                        if key in payload:
                            summary[key] = payload[key]
                elif event.get("type") == "turn_context":
                    for key in ("model", "effort", "sandbox_policy", "permission_profile"):
                        if key in payload:
                            summary[key] = payload[key]
                elif event.get("type") == "response_item" and payload.get("type") in (
                        "function_call", "function_call_output", "custom_tool_call",
                        "custom_tool_call_output", "agent_message"):
                    tool_items.append(event)
            if summary:
                sessions.append(summary)
                (trace_directory / path.name).write_text(
                    "".join(json.dumps(item) + "\n" for item in tool_items))
        metadata["sessions"] = sessions
        roles = {session.get("agent_role") for session in sessions
                 if session.get("agent_role")}
        expected_roles = {
            "probe": {f"argus-{specialty}" for specialty in SPECIALTIES},
            "performance": {"argus-performance"},
            "general": {"argus-correctness", "argus-performance"},
            "clean": {"argus-correctness", "argus-performance"},
            "naming": {"argus-simplicity"},
            "failure": {"argus-correctness", "argus-performance"},
        }[args.case]
        metadata["routing_correct"] = roles == expected_roles
        report_path = output / "report.txt"
        report = report_path.read_text() if report_path.exists() else ""
        metadata["probe_markers_verified"] = all(marker in report for marker in markers.values())
        evidence_fixture = output / "fixture"
        evidence_fixture.mkdir()
        for path in repo.iterdir():
            if path.is_file() and (path.suffix == ".py" or path.name == "AGENTS.md"):
                shutil.copyfile(path, evidence_fixture / path.name)
        (evidence_fixture / "baseline_inventory.py").write_text(BASE_SOURCE)
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        verified = before == after and metadata["routing_correct"] and metadata["probe_markers_verified"]
        print(f"Evidence: {output}; source unchanged: {before == after}; routing: {roles}", flush=True)
        return result.returncode if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
