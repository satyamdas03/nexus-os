"""NEXUS OS CLI."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from nexus_os.agents.runner import AgentRunner
from nexus_os.memory.resume import can_resume
from nexus_os.pipeline.orchestrator import MicroOrchestrator
from nexus_os.reporting.status_report import render_status_report
from nexus_os.roster.loader import load_roster

app = typer.Typer(
    name="nexus-os",
    help="NEXUS OS — a reboot-proof multi-agent operating system.",
    no_args_is_help=True,
)
roster_app = typer.Typer(help="Inspect The Agency roster")
app.add_typer(roster_app, name="roster")
console = Console()


_REPO_OPTION = typer.Option(Path.cwd(), help="Path to the target repository")


@roster_app.command(name="load")
def roster_load() -> None:
    """Load and cache the full Agency roster."""
    roster = load_roster()
    console.print(f"[green]Loaded {len(roster.agents)} agents across {len(roster.divisions)} divisions.[/green]")


@roster_app.command(name="list")
def roster_list(
    division: str | None = typer.Option(None, help="Filter by division slug"),
) -> None:
    """List agents in the roster."""
    roster = load_roster()
    table = Table(title="NEXUS OS Agent Roster")
    table.add_column("Division", style="cyan", no_wrap=True)
    table.add_column("Slug", style="magenta")
    table.add_column("Name", style="green")
    table.add_column("Description")

    agents = roster.agents
    if division:
        agents = [a for a in agents if a.division == division]

    for agent in agents:
        table.add_row(agent.division, agent.slug, agent.name, agent.description[:60])
    console.print(table)
    console.print(f"\nTotal: {len(agents)} agents")


@roster_app.command(name="info")
def roster_info(slug: str) -> None:
    """Show details for a single agent."""
    roster = load_roster()
    agent = roster.by_slug(slug)
    if not agent:
        console.print(f"[red]Agent '{slug}' not found.[/red]")
        raise typer.Exit(code=1)
    console.print(f"[bold]{agent.name}[/bold] ({agent.slug})")
    console.print(f"Division: {agent.division}")
    console.print(f"Description: {agent.description}")
    if agent.vibe:
        console.print(f"Vibe: {agent.vibe}")
    console.print(f"\n[dim]{agent.activation_prompt[:500]}...[/dim]")


@app.command()
def init(
    repo: Path = _REPO_OPTION,
    goal: str | None = typer.Option(None, help="Optional initial goal"),
) -> None:
    """Initialize a .nexus-os/ workspace in a target repository."""
    repo = repo.resolve()
    if not repo.exists():
        console.print(f"[red]Repository path does not exist: {repo}[/red]")
        raise typer.Exit(code=1)

    orchestrator = MicroOrchestrator(repo)
    state = orchestrator.init(
        goal=goal or "NEXUS OS workspace initialized",
        agents=[],
    )
    console.print(f"[green]Initialized NEXUS workspace at {repo / '.nexus-os'}[/green]")
    console.print(f"Status: {state.status}")


@app.command()
def micro(
    repo: Path = _REPO_OPTION,
    goal: str = typer.Option(..., help="Goal for the micro run"),
    agents: str = typer.Option(..., help="Comma-separated agent slugs"),
    dry_run: bool = typer.Option(False, help="Run in dry-run mode (no LLM calls)"),
) -> None:
    """Run a NEXUS-Micro pipeline."""
    repo = repo.resolve()
    if can_resume(repo):
        console.print("[yellow]An interrupted run exists. Use `nexus-os resume` to continue, or delete .nexus-os/state.json.[/yellow]")
        raise typer.Exit(code=1)

    agent_slugs = [s.strip() for s in agents.split(",") if s.strip()]
    roster = load_roster()
    missing = [s for s in agent_slugs if roster.by_slug(s) is None]
    if missing:
        console.print(f"[red]Unknown agent slugs: {', '.join(missing)}[/red]")
        raise typer.Exit(code=1)

    runner = AgentRunner(project_path=repo) if not dry_run else None
    orchestrator = MicroOrchestrator(repo, runner=runner)
    state = orchestrator.init(goal=goal, agents=agent_slugs)
    state = orchestrator.plan(state, goal=goal, agents=agent_slugs)
    state = orchestrator.run(state)

    console.print(render_status_report(state))
    if state.status == "completed":
        console.print("[green]Micro run completed.[/green]")
    else:
        console.print("[red]Micro run did not complete successfully.[/red]")
        raise typer.Exit(code=1)


@app.command()
def resume(
    repo: Path = _REPO_OPTION,
    dry_run: bool = typer.Option(False, help="Run in dry-run mode (no LLM calls)"),
) -> None:
    """Resume an interrupted NEXUS run."""
    repo = repo.resolve()
    if not can_resume(repo):
        console.print("[red]No interrupted run found in this repository.[/red]")
        raise typer.Exit(code=1)

    runner = AgentRunner(project_path=repo) if not dry_run else None
    orchestrator = MicroOrchestrator(repo, runner=runner)
    state = orchestrator.resume()

    console.print(render_status_report(state))
    if state.status == "completed":
        console.print("[green]Resumed run completed.[/green]")
    else:
        console.print("[red]Resumed run did not complete successfully.[/red]")
        raise typer.Exit(code=1)


@app.command()
def sprint(
    repo: Path = _REPO_OPTION,
    goal: str = typer.Option(..., help="Goal for the sprint"),
) -> None:
    """NEXUS-Sprint mode (stub)."""
    console.print(f"[yellow]NEXUS-Sprint is not yet implemented. Goal recorded: {goal}[/yellow]")


@app.command()
def full(
    idea: str = typer.Option(..., help="Idea or project description"),
) -> None:
    """NEXUS-Full mode (stub)."""
    console.print(f"[yellow]NEXUS-Full is not yet implemented. Idea recorded: {idea}[/yellow]")


if __name__ == "__main__":
    app()
