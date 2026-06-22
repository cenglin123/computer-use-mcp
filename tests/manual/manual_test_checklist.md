## SAP Fast Path Performance Smoke Test

- [ ] Start from desktop with SAP Logon closed.
- [ ] Start a CU task session.
- [ ] Take one orientation screenshot.
- [ ] Execute the SAP fast-path batch from `docs/recipes/sap-logon-fast-path.md`.
- [ ] Confirm final screenshot shows SAP login form with username filled and password masked.
- [ ] Confirm no login submit action was sent unless explicitly requested.
- [ ] Confirm elapsed wall-clock time is <= 60 seconds under normal desktop conditions.
- [ ] If elapsed time exceeds 60 seconds, inspect `timing_breakdown.agent_gap_duration_ms` and list the slowest phase.
