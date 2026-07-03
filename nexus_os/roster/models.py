"""Models for The Agency roster."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class Division(BaseModel):
    """A division (category) of agents."""

    slug: str
    label: str
    icon: str
    color: str
    agent_count: int = 0


class Agent(BaseModel):
    """A single agent from The Agency roster."""

    slug: str
    division: str
    name: str
    description: str
    color: str | None = None
    emoji: str | None = None
    vibe: str | None = None
    body: str = ""
    source_path: Path

    @property
    def activation_prompt(self) -> str:
        """Return a minimal NEXUS activation prompt for this agent."""
        lines = [
            f"You are {self.name}.",
            f"Division: {self.division}",
            f"Description: {self.description}",
        ]
        if self.vibe:
            lines.append(f"Vibe: {self.vibe}")
        lines.append("\n" + self.body[:2000])
        if len(self.body) > 2000:
            lines.append("\n[Persona truncated for activation; full source is available in context.]")
        return "\n".join(lines)


class Roster(BaseModel):
    """The complete loaded roster."""

    divisions: list[Division] = Field(default_factory=list)
    agents: list[Agent] = Field(default_factory=list)

    def by_division(self, division_slug: str) -> list[Agent]:
        return [a for a in self.agents if a.division == division_slug]

    def by_slug(self, slug: str) -> Agent | None:
        for agent in self.agents:
            if agent.slug == slug:
                return agent
        return None

    def search(self, query: str) -> list[Agent]:
        query = query.lower()
        return [
            a
            for a in self.agents
            if query in a.name.lower()
            or query in a.description.lower()
            or query in a.body.lower()
            or query in a.division.lower()
        ]
