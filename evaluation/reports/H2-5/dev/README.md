# H2-5 dev artifacts

- `20261027T094246Z-e630bbc4` — **authoritative locked calibration**; its
  `semantic/semantic_calibration.json` is the threshold used by the test run.
- `20261027T093911Z-02979801` — invalid attempt. The adapter added
  `frozen_chunk_id` to candidate dictionaries before `_finalize_rag`; the
  `RetrievalHit` model forbids extras, so all finalizations were marked
  `degraded`. Retained as debugging evidence; not used.
- `20261027T093521Z-eeac4765` — earlier failed attempt before publication
  vectors were included in the precompute. Not used.

The top-level `calibration.json` points only to the authoritative run.
