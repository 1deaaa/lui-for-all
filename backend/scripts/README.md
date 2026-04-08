# backend/scripts

This directory contains non-production helper scripts.

## Structure

- `maintenance/`
  - Data fix or one-time migrations.
  - Examples: `fix_http_calls_metadata.py`, `migrate_messages_id.py`.
- `devtools/`
  - Developer utility scripts.
  - Examples: `list_projects.py`, `list_capabilities.py`, `init_matchbox.py`.
- `manual/`
  - Manual debugging/experiment scripts, not CI tests.
  - Includes archived stream and graph debug scripts.
- `mcp_verify.py`
  - MCP handshake verification flow.

## Notes

- Scripts under `manual/` may require local services and environment variables.
- Automated assertions should live under `backend/test/` as pytest tests.
