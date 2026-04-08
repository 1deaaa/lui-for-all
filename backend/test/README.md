# backend/test

This directory is reserved for automated pytest tests.

Current scope:

- `test_route_extractor_representative_samples.py`
  - Validates representative two-level extraction:
    - Route discovery (`extract_all_routes`)
    - Handler/function extraction (`extract_batch`)

Manual exploratory scripts were moved to `backend/scripts/manual/`.
