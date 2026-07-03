"""Load The Agency roster from the vendored submodule."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from nexus_os.config import Settings, get_settings
from nexus_os.roster.models import Agent, Division, Roster


def _slug_from_filename(path: Path) -> str:
    """Return the agent slug from a markdown filename."""
    return path.stem


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter and return metadata plus body."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta_text = parts[1].strip()
    body = parts[2].strip()
    try:
        meta = yaml.safe_load(meta_text) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, body


def load_divisions(vendor_dir: Path | None = None) -> list[Division]:
    """Load division metadata from divisions.json."""
    settings = get_settings()
    path = (vendor_dir or settings.vendor_dir) / "divisions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    divisions = []
    for slug, info in data.get("divisions", {}).items():
        divisions.append(
            Division(
                slug=slug,
                label=info.get("label", slug),
                icon=info.get("icon", ""),
                color=info.get("color", ""),
            )
        )
    return divisions


def load_agent_file(path: Path, division_slug: str) -> Agent | None:
    """Load a single agent markdown file."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    meta, body = _parse_frontmatter(text)
    if not meta.get("name"):
        return None
    return Agent(
        slug=_slug_from_filename(path),
        division=division_slug,
        name=meta.get("name", path.stem),
        description=meta.get("description", ""),
        color=meta.get("color"),
        emoji=meta.get("emoji"),
        vibe=meta.get("vibe"),
        body=body,
        source_path=path,
    )


def load_roster(vendor_dir: Path | None = None, settings: Settings | None = None) -> Roster:
    """Load the complete Agency roster."""
    if settings is None:
        settings = get_settings()
    vendor = vendor_dir or settings.vendor_dir
    divisions = load_divisions(vendor)
    roster = Roster(divisions=divisions)

    division_slugs = {d.slug for d in divisions}
    for division_slug in division_slugs:
        division_dir = vendor / division_slug
        if not division_dir.exists():
            continue
        for md_file in sorted(division_dir.rglob("*.md")):
            agent = load_agent_file(md_file, division_slug)
            if agent:
                roster.agents.append(agent)

    # Update agent counts
    counts: dict[str, int] = {}
    for agent in roster.agents:
        counts[agent.division] = counts.get(agent.division, 0) + 1
    for division in roster.divisions:
        division.agent_count = counts.get(division.slug, 0)

    return roster
