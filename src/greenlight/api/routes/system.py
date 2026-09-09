from fastapi import APIRouter

from ...config import settings
from ...db.client import query

router = APIRouter()


@router.get("/system/grafana")
async def system_grafana():
    """Externally shared dashboard link for the UI's 'Open in Grafana' button."""
    return {"public_dashboard_url": settings.grafana_public_dashboard_url}


@router.get("/system/schema")
async def system_schema():
    tables = query(
        """
        SELECT name, engine, total_rows, formatReadableSize(total_bytes)
        FROM system.tables WHERE database = 'greenlight' ORDER BY name
        """
    )
    result = []
    for name, engine, rows, size in tables:
        cols = query(f"DESCRIBE TABLE greenlight.{name}")
        result.append(
            {
                "name": name,
                "engine": engine,
                "row_count": int(rows or 0),
                "size": size,
                "columns": [{"name": c[0], "type": c[1], "default": c[3] or ""} for c in cols],
            }
        )
    return {"database": "greenlight", "tables": result}
