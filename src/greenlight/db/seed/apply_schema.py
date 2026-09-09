import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from greenlight.config import settings  # noqa: E402


def apply_schema():
    schema_path = Path(__file__).parent.parent / "schema.sql"
    content = schema_path.read_text()

    statements = []
    current = []
    paren_depth = 0

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        paren_depth += stripped.count("(") - stripped.count(")")
        current.append(line)
        if stripped.endswith(";") and paren_depth == 0:
            stmt = "\n".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []

    root_url = settings.clickhouse_url.rstrip("/")
    base_url = f"{root_url}/?database={settings.clickhouse_db}"

    def _client() -> httpx.Client:
        if settings.clickhouse_password:
            return httpx.Client(auth=(settings.clickhouse_user, settings.clickhouse_password))
        return httpx.Client()

    with _client() as client:
        for i, stmt in enumerate(statements):
            if stmt.strip().upper().startswith("USE "):
                continue
            if stmt.strip().upper().startswith("CREATE DATABASE"):
                r = client.post(f"{root_url}/", content=stmt, timeout=30)
            else:
                r = client.post(base_url, content=stmt, timeout=30)
            if r.status_code != 200 or r.text.strip():
                print(f"FAIL [{i}]: {r.text.strip()[:120]}")
            else:
                label = stmt[:70].replace("\n", " ")
                print(f"OK: {label}...")

    with _client() as client:
        r = client.post(
            base_url,
            content=f"SELECT name FROM system.tables WHERE database='{settings.clickhouse_db}' ORDER BY name",
        )
        tables = [t for t in r.text.strip().split("\n") if t]
        print(f"\n{len(tables)} tables in {settings.clickhouse_db}:")
        for t in tables:
            print(f"  - {t}")


if __name__ == "__main__":
    apply_schema()
