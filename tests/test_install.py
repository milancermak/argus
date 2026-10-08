"""CLI tests use copied bundles and isolated homes, never the user's config."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


INSTALLER = Path(__file__).resolve().parents[1] / "install.py"


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        shutil.copyfile(INSTALLER, self.bundle / "install.py")
        self.skill = self.bundle / "skills" / "argus"
        (self.skill / "references" / "nested").mkdir(parents=True)
        (self.skill / "agents").mkdir()
        (self.skill / "SKILL.md").write_text("---\nname: argus\ndescription: Review code.\n---\nReview.\n")
        (self.skill / "references" / "nested" / "new-reference.md").write_text("Recursive reference.\n")
        (self.skill / "agents" / "openai.yaml").write_text("interface:\n  display_name: Argus\n")
        (self.bundle / "agents").mkdir()
        (self.bundle / "agents" / "argus-correctness.toml").write_text('name = "argus-correctness"\n')
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.environment = dict(os.environ, HOME=str(self.home), PATH=str(self.bin),
                                PYTHONDONTWRITEBYTECODE="1")
        self.environment.pop("CODEX_HOME", None)
        self.dest_skill = self.home / ".agents" / "skills" / "argus"
        self.dest_agents = self.home / ".codex" / "agents"
        self.manifest = self.dest_agents / ".argus-manifest.json"

    def cli(self, *args, success=True, environment=None):
        result = subprocess.run([sys.executable, str(self.bundle / "install.py"), *map(str, args)],
                                capture_output=True, text=True,
                                env=self.environment if environment is None else environment)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def snapshot(self, directory=None):
        return {str(path.relative_to(directory or self.home)): path.read_bytes()
                for path in (directory or self.home).rglob("*") if path.is_file()}

    def test_personal_recursive_payload_and_identical_repeat(self):
        self.cli()
        self.assertEqual((self.dest_skill / "references/nested/new-reference.md").read_text(),
                         "Recursive reference.\n")
        self.assertTrue((self.dest_skill / "agents/openai.yaml").is_file())
        self.assertTrue((self.dest_agents / "argus-correctness.toml").is_file())
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual(manifest["files"]["skill/SKILL.md"],
                         hashlib.sha256((self.skill / "SKILL.md").read_bytes()).hexdigest())
        before = self.snapshot()
        self.assertIn("0 file changes", self.cli().stdout)
        self.assertEqual(before, self.snapshot())

    def test_config_and_unrelated_files_are_preserved(self):
        config = self.home / ".codex/config.toml"
        config.parent.mkdir()
        config.write_text('[agents.personal]\nconfig_file = "personal.toml"\n')
        self.dest_agents.mkdir()
        unrelated = self.dest_agents / "personal.toml"
        unrelated.write_text('name = "personal"\n')
        self.cli()
        unknown = self.dest_skill / "notes.md"
        unknown.write_text("User notes.\n")
        self.cli("--uninstall")
        self.assertEqual(config.read_text(), '[agents.personal]\nconfig_file = "personal.toml"\n')
        self.assertEqual(unrelated.read_text(), 'name = "personal"\n')
        self.assertEqual(unknown.read_text(), "User notes.\n")
        self.assertFalse(self.manifest.exists())
        self.assertFalse((self.dest_skill / "SKILL.md").exists())

    def test_update_requires_flag_and_updates_only_owned_files(self):
        self.cli()
        (self.skill / "SKILL.md").write_text("New skill.\n")
        before = self.snapshot()
        self.assertIn("--update", self.cli(success=False).stderr)
        self.assertEqual(before, self.snapshot())
        self.cli("--update")
        self.assertEqual((self.dest_skill / "SKILL.md").read_text(), "New skill.\n")
        self.cli()

    def test_update_adds_recursive_files_and_removes_obsolete_owned_files(self):
        self.cli()
        (self.skill / "references/nested/new-reference.md").unlink()
        (self.skill / "references/extra.txt").write_text("Another file.\n")
        self.cli("--update")
        self.assertFalse((self.dest_skill / "references/nested/new-reference.md").exists())
        self.assertEqual((self.dest_skill / "references/extra.txt").read_text(), "Another file.\n")
        self.assertFalse((self.dest_skill / "references/nested").exists())

    def test_edited_owned_file_blocks_update_and_uninstall_before_mutation(self):
        self.cli()
        (self.dest_skill / "references/nested/new-reference.md").write_text("User edit.\n")
        (self.skill / "SKILL.md").write_text("Updated bundle.\n")
        before = self.snapshot()
        for mode in ("--update", "--uninstall"):
            self.assertIn("was edited", self.cli(mode, success=False).stderr)
            self.assertEqual(before, self.snapshot())

    def test_missing_owned_file_is_preserved_by_update_but_uninstall_succeeds(self):
        self.cli()
        (self.dest_skill / "SKILL.md").unlink()
        before = self.snapshot()
        self.assertIn("is missing", self.cli("--update", success=False).stderr)
        self.assertEqual(before, self.snapshot())
        self.cli("--uninstall")
        self.assertFalse(self.manifest.exists())

    def test_initial_conflict_has_no_partial_install(self):
        self.dest_agents.mkdir(parents=True)
        conflict = self.dest_agents / "argus-correctness.toml"
        conflict.write_text("User reviewer.\n")
        before = self.snapshot()
        self.assertIn("conflicts", self.cli(success=False).stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.dest_skill.exists())

    def test_identical_unowned_file_is_not_adopted(self):
        self.dest_skill.mkdir(parents=True)
        shutil.copyfile(self.skill / "SKILL.md", self.dest_skill / "SKILL.md")
        before = self.snapshot()
        self.assertIn("not owned", self.cli(success=False).stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.manifest.exists())

    def test_update_conflict_for_new_file_has_no_partial_changes(self):
        self.cli()
        (self.skill / "SKILL.md").write_text("Updated skill.\n")
        (self.skill / "references/new.md").write_text("Bundle reference.\n")
        (self.dest_skill / "references/new.md").write_text("User reference.\n")
        before = self.snapshot()
        self.cli("--update", success=False)
        self.assertEqual(before, self.snapshot())

    def test_update_does_not_adopt_identical_unowned_new_file(self):
        self.cli()
        (self.skill / "SKILL.md").write_text("Updated skill.\n")
        (self.skill / "references/new.md").write_text("Identical reference.\n")
        shutil.copyfile(self.skill / "references/new.md", self.dest_skill / "references/new.md")
        before = self.snapshot()
        self.assertIn("not owned", self.cli("--update", success=False).stderr)
        self.assertEqual(before, self.snapshot())
        self.cli("--uninstall")
        self.assertEqual((self.dest_skill / "references/new.md").read_text(), "Identical reference.\n")

    @unittest.skipUnless(os.name == "posix" and os.geteuid() != 0,
                         "requires enforced POSIX directory permissions")
    def test_write_failure_rolls_back_files_and_new_directories(self):
        self.dest_agents.mkdir(parents=True)
        self.dest_agents.chmod(0o500)
        self.addCleanup(self.dest_agents.chmod, 0o700)
        before = self.snapshot()
        self.assertIn("rolled back", self.cli(success=False).stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.dest_skill.exists())
        self.assertEqual(list(self.dest_agents.iterdir()), [])

    def test_injected_io_failure_restores_original_bytes(self):
        spec = importlib.util.spec_from_file_location("argus_installer_test", INSTALLER)
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        existing = self.home / "existing.txt"
        existing.write_bytes(b"Original bytes.\n")
        new = self.home / "new" / "nested.txt"
        write = installer.atomic_write
        calls = 0

        def fail_second_write(path, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("Injected disk failure")
            write(path, data)

        with mock.patch.object(installer, "atomic_write", side_effect=fail_second_write):
            with self.assertRaises(installer.InstallError):
                installer.apply({existing: b"Changed bytes.\n", new: b"New bytes.\n"})
        self.assertEqual(existing.read_bytes(), b"Original bytes.\n")
        self.assertFalse(new.parent.exists())

    def test_dry_run_does_not_create_destinations(self):
        self.assertIn("preflight passed", self.cli("--dry-run").stdout)
        self.assertEqual(self.snapshot(), {})
        self.cli()
        before = self.snapshot()
        self.cli("--uninstall", "--dry-run")
        self.assertEqual(before, self.snapshot())

    def test_project_scope_ignores_environment_and_preserves_project_config(self):
        project = self.root / "project"
        project.mkdir()
        config = project / ".codex/config.toml"
        config.parent.mkdir()
        config.write_text("# Existing project settings\n")
        environment = dict(self.environment, CODEX_HOME=str(self.root / "external-codex"))
        self.cli("--project", project, environment=environment)
        self.assertTrue((project / ".agents/skills/argus/SKILL.md").is_file())
        self.assertTrue((project / ".codex/agents/argus-correctness.toml").is_file())
        self.assertEqual(config.read_text(), "# Existing project settings\n")
        self.assertFalse((self.root / "external-codex").exists())
        self.assertEqual(self.snapshot(), {})
        self.cli("--project", project, "--uninstall", environment=environment)
        self.assertEqual(config.read_text(), "# Existing project settings\n")

    def test_home_and_codex_home_precedence(self):
        isolated = self.root / "isolated-home"
        env_codex = self.root / "environment-codex"
        explicit_codex = self.root / "explicit-codex"
        environment = dict(self.environment, CODEX_HOME=str(env_codex))
        self.cli("--home", isolated, environment=environment)
        self.assertTrue((isolated / ".agents/skills/argus/SKILL.md").is_file())
        self.assertTrue((env_codex / "agents/argus-correctness.toml").is_file())
        self.cli("--home", isolated, "--uninstall", environment=environment)
        self.cli("--home", isolated, "--codex-home", explicit_codex, environment=environment)
        self.assertTrue((explicit_codex / "agents/argus-correctness.toml").is_file())
        self.assertFalse((isolated / ".codex").exists())
        self.assertEqual(self.snapshot(), {})

    def test_project_rejects_personal_overrides(self):
        for override in ("--home", "--codex-home"):
            self.cli("--project", self.root / "project", override, self.home, success=False)
        self.assertEqual(self.snapshot(), {})

    def test_symlink_parents_and_files_are_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.home / ".agents").symlink_to(outside, target_is_directory=True)
        self.assertIn("Symlink", self.cli(success=False).stderr)
        self.assertEqual(list(outside.iterdir()), [])
        (self.home / ".agents").unlink()
        self.dest_agents.mkdir(parents=True)
        (self.dest_agents / "argus-correctness.toml").symlink_to(outside / "missing")
        self.assertIn("Symlink", self.cli(success=False).stderr)
        self.assertFalse(self.dest_skill.exists())

    def test_selected_root_alias_is_canonicalized(self):
        alias = self.root / "home-alias"
        alias.symlink_to(self.home, target_is_directory=True)
        self.cli("--home", alias)
        self.assertTrue((self.dest_skill / "SKILL.md").is_file())
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual(manifest["destinations"]["skill"], str(self.dest_skill))
        self.cli("--home", alias, "--uninstall")
        self.assertFalse(self.manifest.exists())

    def test_owned_file_symlink_replacement_blocks_uninstall(self):
        self.cli()
        path = self.dest_skill / "SKILL.md"
        contents = path.read_bytes()
        outside = self.root / "outside.md"
        outside.write_bytes(contents)
        path.unlink()
        path.symlink_to(outside)
        self.assertIn("Symlink", self.cli("--uninstall", success=False).stderr)
        self.assertEqual(outside.read_bytes(), contents)
        self.assertTrue(self.manifest.exists())

    def test_malformed_manifest_and_path_traversal_do_not_delete_files(self):
        self.cli()
        protected = self.home / ".codex/config.toml"
        protected.write_text("Protected.\n")
        manifest = json.loads(self.manifest.read_text())
        manifest["files"]["agents/../config.toml"] = hashlib.sha256(protected.read_bytes()).hexdigest()
        self.manifest.write_text(json.dumps(manifest))
        before = self.snapshot()
        self.assertIn("Invalid manifest path", self.cli("--uninstall", success=False).stderr)
        self.assertEqual(before, self.snapshot())
        self.manifest.write_text("invalid json")
        before = self.snapshot()
        self.assertIn("Cannot use manifest", self.cli("--update", success=False).stderr)
        self.assertEqual(before, self.snapshot())

    def test_manifest_destinations_cannot_be_reused_with_a_different_home(self):
        self.cli()
        before = self.snapshot()
        self.cli("--home", self.root / "other-home", "--codex-home", self.home / ".codex",
                 "--uninstall", success=False)
        self.assertEqual(before, self.snapshot())

    def test_runtime_check_reports_feature_state_and_never_installs(self):
        codex = self.bin / "codex"
        codex.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then\n'
                         '  echo "codex-cli fixture"\nelse\n'
                         '  echo "multi_agent stable true"\nfi\n')
        codex.chmod(0o755)
        result = self.cli("--check")
        self.assertIn("codex-cli fixture", result.stdout)
        self.assertIn("multi_agent feature: enabled", result.stdout)
        self.assertIn("verify agent loading", result.stdout)
        self.assertEqual(self.snapshot(), {})
        codex.write_text('#!/bin/sh\necho "multi_agent stable false"\n')
        self.assertIn("disabled or unavailable", self.cli("--check", success=False).stdout)
        codex.unlink()
        self.assertIn("unavailable", self.cli("--check", success=False).stdout)

    def test_project_runtime_check_uses_personal_codex_home_and_project_cwd(self):
        project = self.root / "project"
        project.mkdir()
        log = self.root / "runtime-check.log"
        codex = self.bin / "codex"
        codex.write_text('#!/bin/sh\n'
                         'printf "%s|%s|%s\\n" "$HOME" "$CODEX_HOME" "$PWD" >> "$ARGUS_TEST_LOG"\n'
                         'if [ "$1" = "--version" ]; then\n'
                         '  echo "codex-cli fixture"\nelse\n'
                         '  echo "multi_agent stable true"\nfi\n')
        codex.chmod(0o755)
        for personal_codex_home in (None, self.root / "custom-codex-home"):
            environment = dict(self.environment, ARGUS_TEST_LOG=str(log))
            if personal_codex_home is not None:
                environment["CODEX_HOME"] = str(personal_codex_home)
            self.cli("--project", project, "--check", environment=environment)
            expected_codex_home = personal_codex_home or self.home / ".codex"
            self.assertEqual(log.read_text().splitlines(),
                             [f"{self.home}|{expected_codex_home}|{project}"] * 2)
            log.unlink()
            self.assertFalse((project / ".codex").exists())
            self.assertFalse(expected_codex_home.exists())
        self.assertEqual(self.snapshot(), {})

    def test_uninstall_without_manifest_preserves_existing_payload(self):
        self.dest_skill.mkdir(parents=True)
        (self.dest_skill / "SKILL.md").write_text("Not installed by Argus.\n")
        before = self.snapshot()
        self.cli("--uninstall", success=False)
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
