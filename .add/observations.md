# Process Observations

2026-11-21 11:08 | deploy | Committed sms-channel (M3) to main (96f6b8b, 13 files, 37/37 tests, ruff clean, secrets gate pass); push to origin blocked by Claude Code permission — awaiting user approval | benefit: feature landed with full gate evidence
2026-11-21 11:17 | deploy | Pushed 96f6b8b + CI fix 77b6c8e (root conftest.py); first green CI run on this repo — bare pytest vs python -m pytest sys.path mismatch had failed every prior run | benefit: CI now actually gates
2026-11-21 11:26 | retro | Second retro of day: M3 window reviewed, L-007/L-008 promoted to library (WL-004/WL-005), sms-channel spec marked Complete, first handoff.md written (remediates recurring adherence fail) | benefit: handoff gap closed
2026-11-21 11:33 | spec | whatsapp-channel spec created (7 ACs, 3 TCs); routing + 24h-window decisions made by human via 2-question condensed interview | benefit: next M3 feature spec'd in minutes
2026-11-21 11:41 | tdd-cycle+verify | whatsapp-channel: strict RED(10 fail)->GREEN(48 pass)->refactor->verify deploy-level; coverage measured 80%; formal /add:verify run for first time | benefit: adherence gaps from retros closed
2026-11-21 11:49 | spec | calendar-sync spec created (7 ACs, 4 TCs); provider + scope decided by human via condensed interview | benefit: final M3 feature spec'd
2026-11-21 11:53 | tdd-cycle+verify | calendar-sync: RED(10 fail)->GREEN(59 pass)->verify; coverage 82%; caught Windows zoneinfo-needs-tzdata via test | benefit: M3 roadmap complete
