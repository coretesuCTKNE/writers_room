import logging
from urllib.parse import urlparse

import clickhouse_connect
from clickhouse_connect.driver.client import Client

from ..config import settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_ch_client() -> Client:
    global _client
    if _client is None:
        parsed = urlparse(settings.clickhouse_url)
        _client = clickhouse_connect.get_client(
            host=parsed.hostname or "localhost",
            port=parsed.port or 8123,
            database=settings.clickhouse_db,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            secure=parsed.scheme == "https",
            # async_insert=1 silently drops blocks on ClickHouse Cloud's
            # SharedReplacingMergeTree (observed: 3 of 5 active_sessions
            # inserts never landed). Write volume here is tiny — synchronous
            # inserts are the correctness-safe default.
        )
    return _client


def ping() -> bool:
    """Cheap connectivity probe. Returns True if SELECT 1 roundtrips."""
    try:
        client = get_ch_client()
        client.command("SELECT 1")
        return True
    except Exception as e:
        logger.warning(f"ClickHouse ping failed: {e}")
        return False


def query(sql: str, parameters: dict | None = None) -> list:
    client = get_ch_client()
    return client.query(sql, parameters=parameters).result_rows


def insert(table: str, data: list[dict]) -> None:
    if not data:
        return
    client = get_ch_client()
    columns = list(data[0].keys())
    values = [list(row.values()) for row in data]
    client.insert(f"{settings.clickhouse_db}.{table}", values, column_names=columns)


def command(sql: str, parameters: dict | None = None) -> None:
    """Execute a DDL/DML statement (CREATE TABLE, ALTER TABLE, etc.)."""
    client = get_ch_client()
    client.command(sql, parameters=parameters or {})
