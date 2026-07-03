# 🌌 NEXUS OS

A **reboot-proof, multi-agent operating system** built on top of [The Agency](https://github.com/msitarzewski/agency-agents) roster. NEXUS OS turns 233 specialized AI agents into a coordinated execution engine that can be dropped into any new or existing project.

> **NEXUS** = **Network of EXperts, Unified in Strategy**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ What is NEXUS OS?

The Agency is a world-class library of specialized AI agents — frontend developers, security architects, growth hackers, evidence collectors, and 200+ more. But a library is not an operating system. **NEXUS OS** provides the runtime:

- **Roster ingestion** — loads every agent from The Agency with full persona and workflow
- **Pipeline execution** — runs NEXUS-Full, NEXUS-Sprint, and NEXUS-Micro pipelines
- **Dev↔QA loops** — pairs developer agents with Evidence Collector and Reality Checker gates
- **Restart-proof memory** — every state change is written to disk and committed to git, so a laptop crash or session restart never loses context
- **Pluggable into any project** — `nexus-os init` creates a `.nexus-os/` workspace in any repo

## 🚀 Quickstart

```bash
# 1. Clone and install
gh repo clone satyamdas03/nexus-os
cd nexus-os
pip install -e ".[dev]"

# 2. Verify the roster loads
nexus-os roster load
nexus-os roster list

# 3. Initialize NEXUS in a target project
nexus-os init --repo ../aura-demo

# 4. Run a targeted micro task
nexus-os micro \
  --repo ../aura-demo \
  --goal "Run the Hermes rules-engine gate regression smoke test" \
  --agents testing-api-tester,testing-evidence-collector

# 5. Resume after a restart or interruption
nexus-os resume --repo ../aura-demo
```

## 🧠 Restart-Proof Memory

NEXUS OS is designed for long-running, autonomous workflows. State is never held only in memory:

| Location | Purpose |
|----------|---------|
| `.nexus-os/state.json` | Current phase, active task, retry counters, selected agents |
| `.nexus-os/checkpoints/` | Named snapshots after every major transition |
| `.nexus-os/handoffs/` | Standard, QA PASS/FAIL, escalation, and phase-gate handoffs |
| `.nexus-os/memory/` | Agent outputs, evidence artifacts, and decision context |
| `.nexus-os/logs/` | Decision log and CLI history |
| `~/.nexus-os/config.yaml` | User-global settings and env-var references |

When run inside a git repository, NEXUS OS auto-commits `.nexus-os/` after every checkpoint. If your laptop restarts, the next session reads `state.json` and can resume exactly where it left off.

## 🏗️ Architecture

```
nexus-os/
├── nexus_os/
│   ├── cli.py              # Typer CLI
│   ├── config.py           # Settings + env vars
│   ├── roster/             # Agent catalog ingestion
│   ├── memory/             # State store + handoffs + resume
│   ├── pipeline/           # Phase state machine + orchestrator
│   ├── agents/             # LLM runner + prompt rendering
│   ├── evidence/           # Evidence Collector + Reality Checker
│   ├── tools/              # Git, filesystem, shell adapters
│   └── reporting/          # Status reports + logs
├── vendor/agency-agents/   # Git submodule (The Agency roster)
├── tests/
└── docs/
```

## 🎭 Execution Modes

| Mode | Timeline | Agents | Use Case |
|------|----------|--------|----------|
| **NEXUS-Micro** | 1–5 days | 5–10 | Targeted task with Dev↔QA loop |
| **NEXUS-Sprint** | 2–6 weeks | 15–25 | Feature or MVP build |
| **NEXUS-Full** | 12–24 weeks | All divisions | Complete product lifecycle |

## 📦 Commands

```bash
nexus-os roster load              # Parse and cache the full Agency roster
nexus-os roster list              # List all agents
nexus-os roster info <slug>       # Show agent details
nexus-os init --repo <path>        # Initialize .nexus-os/ in a project
nexus-os micro --repo <path> ...   # Run a targeted micro task
nexus-os resume --repo <path>      # Resume an interrupted run
```

## 🧪 Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## 🗺️ Roadmap

- [x] Roster ingestion and catalog
- [x] Restart-proof memory store
- [x] NEXUS-Micro prototype
- [x] Evidence Collector + Reality Checker gates
- [ ] NEXUS-Sprint and NEXUS-Full modes
- [ ] MCP tool server integration
- [ ] Browser/screenshot evidence via Playwright
- [ ] Web dashboard for pipeline monitoring

## 🙏 Credits

Built on top of [The Agency](https://github.com/msitarzewski/agency-agents) by Michał Sitarzewski and contributors.

## 📜 License

MIT — see [LICENSE](LICENSE).
