"""Tests for roster ingestion."""

from __future__ import annotations

from nexus_os.roster.loader import load_agent_file, load_divisions, load_roster


def test_load_divisions():
    divisions = load_divisions()
    assert len(divisions) == 16
    slugs = {d.slug for d in divisions}
    assert "engineering" in slugs
    assert "marketing" in slugs


def test_load_roster():
    roster = load_roster()
    assert len(roster.agents) == 233
    assert len(roster.divisions) == 16
    frontend = roster.by_slug("engineering-frontend-developer")
    assert frontend is not None
    assert frontend.division == "engineering"
    assert "Frontend Developer" in frontend.name


def test_search_roster():
    roster = load_roster()
    results = roster.search("security architect")
    assert any("security-architect" in a.slug for a in results)


def test_load_agent_file(tmp_path):
    md = tmp_path / "test-agent.md"
    md.write_text(
        "---\nname: Test Agent\ndescription: A test agent\ncolor: blue\nemoji: 🧪\n---\n\n# Body\n", encoding="utf-8"
    )
    agent = load_agent_file(md, "testing")
    assert agent is not None
    assert agent.name == "Test Agent"
    assert agent.slug == "test-agent"
