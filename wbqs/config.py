#!/usr/bin/env python3
"""Application configuration: load config.ini and resolve which job to run.

A "job" points at the QuickStatements file to import. It can be given as:
  * a CLI target (a .qs file or a test-case folder),
  * ``[job] qs_file``   -> an explicit .qs file,
  * ``[job] job_dir``   -> a folder holding the .qs file (reports go into
    ``<folder>/report``; the old key ``testcase`` still works as an alias), or
  * the legacy ``[import] data_dir`` / ``input_file`` / ``report_dir`` settings.

Relative paths in the config are resolved against the directory of config.ini,
so a run works regardless of the current working directory (e.g. the VS Code
"Run Python File" button).
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path

from .client import DEFAULT_USER_AGENT

# Directory of this file's project root (two levels: wbqs/ -> project).
PROJECT_DIR = Path(__file__).resolve().parent.parent


@dataclass
class AppConfig:
    api_url: str
    username: str
    password: str
    user_agent: str

    qs_file: Path
    report_dir: Path

    dry_run: bool = False
    skip_existing: bool = True
    maxlag: int = 0
    mark_bot: bool = False
    throttle_seconds: float = 0.0

    # True when we fell back to config.example.ini (placeholders only).
    using_example: bool = False


class ConfigError(Exception):
    pass


def _first_existing(names: list[str]) -> Path | None:
    for base in (Path.cwd(), PROJECT_DIR):
        for name in names:
            candidate = base / name
            if candidate.is_file():
                return candidate
    return None


def resolve_config_path(explicit: Path | None) -> tuple[Path, bool]:
    """Locate config.ini. Returns (path, is_example)."""
    if explicit is not None:
        if not explicit.is_file():
            raise ConfigError(f"Config file not found: {explicit}")
        return explicit, False

    real = _first_existing(["config.ini"])
    if real is not None:
        return real, False

    example = _first_existing(["config.example.ini"])
    if example is not None:
        return example, True

    raise ConfigError(
        "No config.ini found. Copy config.example.ini to config.ini and fill in "
        "your credentials."
    )


def _resolve_rel(value: str, base_dir: Path) -> Path:
    """Resolve a possibly-relative config path against base_dir (config location)."""
    p = Path(value).expanduser()
    return p if p.is_absolute() else (base_dir / p)


def _find_qs_in_dir(folder: Path) -> Path:
    if (folder / "input.qs").is_file():
        return folder / "input.qs"
    qs_files = sorted(folder.glob("*.qs"))
    if len(qs_files) == 1:
        return qs_files[0]
    if not qs_files:
        raise ConfigError(f"No .qs file found in test-case folder: {folder}")
    names = ", ".join(p.name for p in qs_files)
    raise ConfigError(
        f"Multiple .qs files in {folder}: {names}. Rename one to input.qs or set "
        "[job] qs_file."
    )


def resolve_job(
    config: configparser.ConfigParser,
    base_dir: Path,
    cli_target: Path | None,
) -> tuple[Path, Path]:
    """Return (qs_file, report_dir) for the job to run."""
    # 1) Explicit CLI target: a file or a test-case folder.
    if cli_target is not None:
        target = cli_target.expanduser()
        if target.is_dir():
            return _find_qs_in_dir(target), target / "report"
        if target.is_file():
            return target, target.parent / "report"
        raise ConfigError(f"Target not found: {target}")

    # 2) [job] qs_file
    qs_file = config.get("job", "qs_file", fallback="").strip()
    if qs_file:
        p = _resolve_rel(qs_file, base_dir)
        if not p.is_file():
            raise ConfigError(f"[job] qs_file not found: {p}")
        return p, p.parent / "report"

    # 3) [job] job_dir folder (alias: testcase, kept for backwards compat)
    job_dir = (
        config.get("job", "job_dir", fallback="").strip()
        or config.get("job", "testcase", fallback="").strip()
    )
    if job_dir:
        d = _resolve_rel(job_dir, base_dir)
        if not d.is_dir():
            raise ConfigError(f"[job] job_dir folder not found: {d}")
        return _find_qs_in_dir(d), d / "report"

    # 4) Legacy [import] data_dir / input_file / report_dir
    data_dir = _resolve_rel(config.get("import", "data_dir", fallback="data"), base_dir)
    report_dir = _resolve_rel(config.get("import", "report_dir", fallback="report"), base_dir)
    input_file = config.get("import", "input_file", fallback="").strip()
    if input_file:
        p = _resolve_rel(input_file, data_dir if not Path(input_file).is_absolute() else base_dir)
        if not p.is_file():
            raise ConfigError(f"[import] input_file not found: {p}")
        return p, report_dir
    if data_dir.is_dir():
        return _find_qs_in_dir(data_dir), report_dir

    raise ConfigError(
        "No job configured. Set [job] job_dir (or qs_file) in config.ini, or pass "
        "a .qs file / job folder on the command line."
    )


def load(
    config_path: Path | None,
    cli_target: Path | None = None,
    *,
    cli_dry_run: bool = False,
    cli_no_skip_existing: bool = False,
) -> AppConfig:
    path, using_example = resolve_config_path(config_path)
    config = configparser.ConfigParser()
    if not config.read(path, encoding="utf-8"):
        raise ConfigError(f"Could not read config: {path}")

    base_dir = path.resolve().parent
    qs_file, report_dir = resolve_job(config, base_dir, cli_target)

    username = os.environ.get("WIKIBASE_USERNAME") or config.get("wikibase", "username", fallback="").strip()
    password = os.environ.get("WIKIBASE_PASSWORD") or config.get("wikibase", "password", fallback="")
    ua_cfg = config.get("wikibase", "user_agent", fallback=DEFAULT_USER_AGENT).strip()
    user_agent = ua_cfg or DEFAULT_USER_AGENT

    dry_run = cli_dry_run or config.getboolean("import", "dry_run", fallback=False) or using_example
    skip_existing = config.getboolean("import", "skip_existing", fallback=True)
    if cli_no_skip_existing:
        skip_existing = False

    return AppConfig(
        api_url=config.get("wikibase", "api_url", fallback="").strip(),
        username=username,
        password=password,
        user_agent=user_agent,
        qs_file=qs_file,
        report_dir=report_dir,
        dry_run=dry_run,
        skip_existing=skip_existing,
        maxlag=config.getint("import", "maxlag", fallback=0),
        mark_bot=config.getboolean("import", "mark_bot", fallback=False),
        throttle_seconds=config.getfloat("import", "throttle_seconds", fallback=0.0),
        using_example=using_example,
    )