"""Print the SQLite schema. Run this before ingesting anything.

    uv run python -m cost_engine.scripts.show_schema
"""

from __future__ import annotations

from ..db import schema_sql


def main() -> int:
    print(schema_sql())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
