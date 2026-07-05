# ASSURE — 60-second walkthrough

1. **Command Centre (heatmap).** "34,000 portfolios. 31,200 aligned. 2,800 breached, 1,200 drifting. The summary bar reads the whole book in plain English before you click anything." Point at red blocks — tile size is FUM and tiles are sorted by FUM (largest top-left), so every view shows a mixed red/orange/green picture rather than pushing all greens to the back.
2. **Market Panel.** "This book moves. A seeded market model ticks forward, and breaches emerge from real drift." Click **Tick** or **Advance 5 days** to watch the summary counts shift.
3. **Click the biggest red block → Diagnosis.** "This is the screen that used to be unreadable. The narrative panel reads the portfolio for you: the engine flagged the breaches; the AI just translates them to plain English."
4. **Click a breach chip** → offending holdings highlight in the table. **Click the "?"** on a row → the AI explains the exact rule that applies to that holding or asset class, not a generic story. The allocation bar chart also exposes Explain per asset class.
5. **Confidence line:** "Every rule check is deterministic — 100% rule maths. The narrative is advisory. The rules engine decides compliance, not the AI."
6. **Go to Workbench → "Propose a fix."** AI proposes minimal compliant trades (e.g. trim the over-weight holding, add a compliant one). The verification panel simulates the resulting portfolio and re-runs the rules.
7. **Verification panel lights up:** ✅✅✅ — "AI recommends… assurance verifies. The AI doesn't get the final say — this rules engine does. If it's still red, the agent retries once."
8. **Click Approve.** Status flips green. Audit trail shows every step with timestamp + who + why (ai / engine / human, advisory / deterministic). "Human in the loop, fully audited. Nothing happens without a person." You can also export the remediation plan as an RFC-4180 CSV.
9. **Learning chip:** "Over time it learns your team's preferences — but only ever suggests, never overrides."
10. **Close:** "Today this is three slow, manual, spreadsheet-bound screens. Same data, same accuracy, same human control — made intuitive, explained, semi-automated. That's the V1-to-V2 jump. **AI recommends. Assurance verifies.**"

## Run locally

```bash
# backend
cd backend
python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe generators/generate_data.py   # seeds data/aura.db with 34,000 portfolios
.venv/Scripts/uvicorn main:app --port 8000

# frontend (other terminal)
cd frontend
npm install
npm run dev   # http://localhost:3000
```

With no `ANTHROPIC_API_KEY` set the backend uses `MockLLM` (deterministic, offline). Set the key for real Claude narratives.

## Voice — Conversational Assurance

Open any portfolio and click **Ask ASSURE**.

- **Browser fallback:** the microphone button captures your question with the browser's SpeechRecognition API and reads the grounded answer with SpeechSynthesis. No credentials needed.
- **LiveKit upgrade:** set `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` in the backend environment. The drawer will show a headset icon. Click it to join the real-time room.

To run the server-side voice agent (handles speech bi-directionally):

```bash
cd backend
export LIVEKIT_URL=wss://your-project.livekit.cloud
export LIVEKIT_API_KEY=...
export LIVEKIT_API_SECRET=...
export DEEPGRAM_API_KEY=...   # STT
export OPENAI_API_KEY=...     # TTS
export ASSURE_API_BASE=http://127.0.0.1:8000
python -m agents.livekit_assistant --client-id <CLIENT_ID>
```

The agent joins the same room the frontend entered, transcribes the user's speech, calls `/portfolio/{client_id}/chat`, and speaks the grounded answer.

---

# Phase 2 — Hermes, the self-improving assurance engine (demo path)

Hermes is the headline Phase 2 feature: an autonomous **book-wide** remediation engine, caged by deterministic assurance + a human approver. Start from a clean book: `POST /admin/reset` (or the reset button) clears the shadow state so all 34,000 portfolios return to their immutable seed.

11. **Open `/hermes` (Mission Control).** "This is the engine room. Hermes scans the whole book at once, not one portfolio at a time." Read the safety-cage banner: **mandate rules = law (deterministic only); remediation strategy = judgment (Hermes-tunable).** Hermes reflection writes only `strategy.yaml`.

12. **Click "Scan Book".** Hermes runs every effective portfolio through the proposer, then **gates each proposal through the deterministic rules engine**. The queue shows only compliant proposals (post-trade green/orange), ranked by FUM × severity. Misses — proposals the gate dropped because they were still red — appear below. "AI proposes, assurance verifies, at book scale. The gate is the rules engine, not the AI." Scan state is persisted to a pluggable Hermes store so the queue survives restarts.

13. **Book Score panel.** Composite of alignment rate (green share), acceptance rate (human approves of AI proposals, read from the audit trail), avg trades per fix, breaches remaining. "One number for how healthy the book is and how well the human-AI loop is working."

14. **Remediation Strategy panel.** The six judgment variables, each with a value and a rationale. "This is the only thing Hermes is allowed to change. The mandate rules above are locked."

15. **Click "Reflect (deterministic)."** Hermes reads the latest heartbeat + score and proposes **one** strategy change — e.g. "3 proposals still breached after proportional trim; switch to liquidate." The proposal card shows `variable: current → proposed` + rationale. "It learns from misses. But it only *proposes* — it never self-adopts."

16. **Click "Adopt (human gate)."** The strategy is mutated, the version bumps, the prior snapshot is archived to `history/vN.json`, and an audit entry is written. "A human pressed the button. Versioned and reversible — every change is in history." The Strategy History panel below shows the archived snapshots.

17. **Re-scan.** The new strategy changes the proposer's output (different trim method, different trades). The queue shifts. "The engine just got better — and it did it itself, within the cage."

18. **Approve a batch from the queue.** Select one or more rows and click **Approve Batch**. Each batch is applied through the same human-in-the-loop gate as Workbench, the shadow state updates, and the queue marks those rows processed.

19. **Close:** "Phase 1 made one portfolio readable and gave the AI a verify-loop with a human gate. Phase 2 makes the whole book self-improving: Hermes proposes at scale, the deterministic engine gates every proposal, the human approves, reflection tunes the strategy, and the market model keeps the book alive — never the mandate. **AI recommends. Assurance verifies. Hermes learns — but the law stays the law.**"
