#!/usr/bin/env python3
"""Install only Argus's skill and reviewer files, without changing Codex config."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile


MANIFEST = ".argus-manifest.json"


class InstallError(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def absolute(path):
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def safe_path(path, directory=False):
    """Reject symlinks at the target and every existing parent."""
    for item in reversed((path, *path.parents)):
        if item.is_symlink():
            raise InstallError(f"Symlink destination is unsafe: {item}")
        if item != path and item.exists() and not item.is_dir():
            raise InstallError(f"Parent is not a directory: {item}")
    if path.exists() and (path.is_dir() != directory or not directory and not path.is_file()):
        raise InstallError(f"Unexpected destination type: {path}")


def sources(bundle):
    payload = {}
    for category, directory in (("skill", bundle / "skills" / "argus"),
                                ("agents", bundle / "agents")):
        if not directory.is_dir() or directory.is_symlink():
            raise InstallError(f"Missing source directory: {directory}")
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise InstallError(f"Source symlinks are unsupported: {path}")
            if path.is_file():
                if category == "agents" and not (path.parent == directory and
                                                 path.name.startswith("argus-") and
                                                 path.suffix == ".toml"):
                    continue
                payload[f"{category}/{path.relative_to(directory).as_posix()}"] = path.read_bytes()
    if "skill/SKILL.md" not in payload or not any(key.startswith("agents/") for key in payload):
        raise InstallError("Bundle must contain skills/argus/SKILL.md and agents/argus-*.toml")
    return payload


def target(key, roots):
    category, separator, relative = key.partition("/")
    parts = PurePosixPath(relative).parts
    if not separator or category not in roots or not parts or relative.startswith("/") or \
            any(part in (".", "..") for part in parts) or "\\" in relative:
        raise InstallError(f"Invalid manifest path: {key}")
    if category == "agents" and (len(parts) != 1 or not relative.startswith("argus-") or
                                not relative.endswith(".toml")):
        raise InstallError(f"Invalid reviewer manifest path: {key}")
    return roots[category].joinpath(*parts)


def read_manifest(path, roots):
    if not path.exists():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest["version"] != 1 or manifest["destinations"] != {
                name: str(root) for name, root in roots.items()}:
            raise ValueError("version or destinations do not match")
        owned = manifest["files"]
        if not isinstance(owned, dict):
            raise ValueError("files must be an object")
        for key, checksum in owned.items():
            target(key, roots)
            if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
                raise ValueError("invalid checksum")
        return owned
    except (ValueError, KeyError, TypeError) as error:
        raise InstallError(f"Cannot use manifest {path}: {error}") from error


def preflight(roots, manifest_path, owned, payload, update, uninstall):
    for root in roots.values():
        safe_path(root, directory=True)
    safe_path(manifest_path)
    for key, checksum in (owned or {}).items():
        path = target(key, roots)
        safe_path(path)
        if not path.exists():
            if uninstall:
                continue
            raise InstallError(f"Installed file is missing: {path}; restore it or uninstall first")
        if digest(path.read_bytes()) != checksum:
            raise InstallError(f"Installed file was edited; preserving all files: {path}")
    if uninstall:
        return {target(key, roots): None for key in owned or {} if target(key, roots).exists()}
    changes = {}
    for key, data in payload.items():
        path = target(key, roots)
        safe_path(path)
        current = path.read_bytes() if path.exists() else None
        if current is not None and key not in (owned or {}):
            raise InstallError(f"Destination conflicts with bundle; existing file is not owned: {path}")
        if current == data:
            continue
        if current is not None and (key not in (owned or {}) or not update):
            hint = "; use --update for untouched Argus files" if key in (owned or {}) else ""
            raise InstallError(f"Destination conflicts with bundle: {path}{hint}")
        changes[path] = data
    obsolete = set(owned or {}) - set(payload)
    if obsolete and not update:
        raise InstallError("Bundle file list changed; use --update")
    for key in obsolete:
        changes[target(key, roots)] = None
    return changes


def atomic_write(path, data):
    descriptor, temporary = tempfile.mkstemp(prefix=".argus-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply(changes):
    """Use atomic file writes and roll back ordinary I/O failures."""
    originals = {path: path.read_bytes() if path.exists() else None for path in changes}
    made_directories = []
    completed = []
    try:
        for path, data in changes.items():
            if data is not None:
                missing = []
                parent = path.parent
                while not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                for directory in reversed(missing):
                    directory.mkdir()
                    made_directories.append(directory)
                atomic_write(path, data)
            elif path.exists():
                path.unlink()
            completed.append(path)
    except OSError as error:
        rollback_errors = []
        for path in reversed(completed):
            try:
                if originals[path] is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, originals[path])
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        for directory in reversed(made_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        detail = f"; rollback needs attention: {'; '.join(rollback_errors)}" if rollback_errors else "; rolled back"
        raise InstallError(f"Install failed: {error}{detail}") from error


def clean_empty_directories(paths, roots):
    candidates = set()
    for path in paths:
        parent = path.parent
        while parent in roots.values() or any(root in parent.parents for root in roots.values()):
            candidates.add(parent)
            parent = parent.parent
    for directory in sorted(candidates, key=lambda path: len(path.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def check_runtime(home, codex_home, project=None):
    executable = shutil.which("codex")
    if executable is None:
        print("Codex CLI unavailable. Install Codex to use native reviewer agents.")
        return 1
    environment = dict(os.environ, HOME=str(home), CODEX_HOME=str(codex_home))
    try:
        version = subprocess.run([executable, "--version"], capture_output=True, text=True,
                                 timeout=10, env=environment, cwd=project, check=True)
        print(version.stdout.strip())
        features = subprocess.run([executable, "features", "list"], capture_output=True, text=True,
                                  timeout=10, env=environment, cwd=project, check=True)
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Could not inspect Codex CLI: {error}")
        return 1
    enabled = any(re.fullmatch(r"multi_agent\s+.+\s+true", line.strip())
                  for line in features.stdout.splitlines())
    print(f"multi_agent feature: {'enabled' if enabled else 'disabled or unavailable'}")
    print("This checks CLI presence and feature state. Run an Argus review to verify agent loading.")
    return 0 if enabled else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, metavar="PATH", help="install in one project's local directories")
    parser.add_argument("--home", type=Path, metavar="PATH", help="use an isolated HOME for a personal installation")
    parser.add_argument("--codex-home", type=Path, metavar="PATH", help="override CODEX_HOME for a personal installation")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--update", action="store_true", help="update only untouched installed files")
    mode.add_argument("--uninstall", action="store_true", help="remove only untouched files owned by this installation")
    mode.add_argument("--check", action="store_true", help="inspect Codex version and multi_agent feature without installing")
    parser.add_argument("--dry-run", action="store_true", help="preflight and show the result without writing")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 9):
        parser.error("Python 3.9 or newer is required")
    if args.project and (args.home or args.codex_home):
        parser.error("--project cannot be combined with --home or --codex-home")
    # Canonicalize deliberately selected roots, then check all generated destinations.
    # This accepts platform aliases such as /tmp without accepting a linked .agents.
    home = absolute(args.home or Path.home()).resolve()
    base = absolute(args.project).resolve() if args.project else home
    selected_codex_home = args.codex_home or os.environ.get("CODEX_HOME")
    codex_home = base / ".codex" if args.project else (
        absolute(selected_codex_home).resolve() if selected_codex_home else home / ".codex")
    roots = {"skill": base / ".agents" / "skills" / "argus", "agents": codex_home / "agents"}
    if args.check:
        runtime_codex_home = absolute(selected_codex_home).resolve() if selected_codex_home else home / ".codex"
        return check_runtime(home, runtime_codex_home, base if args.project else None)
    manifest_path = roots["agents"] / MANIFEST
    try:
        for root in roots.values():
            safe_path(root, directory=True)
        safe_path(manifest_path)
        owned = read_manifest(manifest_path, roots)
        if args.uninstall and owned is None:
            raise InstallError(f"No Argus installation manifest: {manifest_path}")
        payload = {} if args.uninstall else sources(Path(__file__).resolve().parent)
        changes = preflight(roots, manifest_path, owned, payload, args.update, args.uninstall)
        if args.uninstall:
            changes[manifest_path] = None
        else:
            manifest = {"version": 1, "destinations": {name: str(root) for name, root in roots.items()},
                        "files": {key: digest(data) for key, data in sorted(payload.items())}}
            data = (json.dumps(manifest, indent=2) + "\n").encode()
            if not manifest_path.exists() or manifest_path.read_bytes() != data:
                changes[manifest_path] = data
        verb = "Uninstall" if args.uninstall else "Install"
        print(f"{verb}: {roots['skill']} and {roots['agents']}")
        if args.dry_run:
            print(f"Dry run: {len(changes)} file changes; preflight passed.")
        else:
            apply(changes)
            clean_empty_directories((path for path, data in changes.items() if data is None), roots)
            print(f"{'Uninstalled' if args.uninstall else 'Installed'} Argus ({len(changes)} file changes).")
            if not args.uninstall and shutil.which("codex") is None:
                print("Warning: Codex CLI unavailable; native reviewer agents have not been verified.", file=sys.stderr)
        return 0
    except (InstallError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
