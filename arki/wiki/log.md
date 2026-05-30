# Wiki log — changelog + promotion pointer

The chronological **promotion / strategy-evolution log** lives in
[`../../docs/arki/strategy_evolution.md`](../../docs/arki/strategy_evolution.md) (the raw source). This
page does **not** duplicate it — it points to it and records changes to the wiki itself. See also
[system/lineage.md](system/lineage.md) for the summarised version spine.

## Wiki changelog

- **2026-05-28** — Wiki bootstrapped (AI-Native layer, Phases 1–4 in one pass). Created `index`,
  `schema`, `log`, `system/{system-card, architecture, lineage, universe}`, `findings/universe-sweep`,
  `process/index`. Pages seeded by summary+link from `docs/arki/*` (no duplication). SessionStart
  prime-card hook added at `.claude/settings.json`; short pointers added to `CLAUDE.md` + `AGENTS.md`.
  Fork-safety verified: zero upstream-tracked files touched. Rationale: `docs/arki/AI_NATIVE_BOOTSTRAP.md`;
  rules: [`../README.md`](../README.md).

- **2026-05-31** — `futures_momentum` family ingest. Reflects the 2026-05-30/31 work batch.

  **Edits**:
  - `system/system-card.md` — Status line now points to the `futures_momentum` research family +
    TBM Stage-1 NO SIGNAL verdict + family DSR threshold 0.3326 ann; new "Research family"
    block added; `last_verified` advanced to 2026-05-31.
  - `index.md` — new sections *Research families — ongoing ARS-governed work* and *Handoffs —
    open / pending action*; *Findings* section gains pointer to new `findings/futures-momentum.md`;
    backlog updated with Stage-2 speed-tilt + paper-family exit candidate.
  - `findings/futures-momentum.md` (new) — pointer-style summary of 14 cells, 4 LESSONS chain
    entries, predict-then-measure scorecard, honest scorecard (process B+ / alpha F /
    prediction 75%).

  **Source artefacts ingested**: `ars/families/futures_momentum/{family.yaml, findings.md, matrix.md, queue.md}`,
  `arki/utils/dsr.py`, `arki/reports/2026-05-31/`, `docs/arki/handoff_*_2026-05-31.md`,
  `docs/arki/session_predictions_scorecard_2026-05-31.md`, `ars/LESSONS.md` (4 sMOM-chain entries).

  **Honest read recorded**: process B+ / alpha F / prediction skill 75% (n=10 suggestive not
  conclusive). Future-evidence threshold: next 30-40 predictions across queued cells either
  confirm or invalidate the 75% baseline.

  Fork-safety preserved: zero upstream-tracked files touched in this batch.
