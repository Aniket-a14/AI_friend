"""Export / import a friend over HTTP (roadmap Phase 4.1 + 5.1).

Thin wrappers around `scripts/export_friend.py` / `import_friend.py` -- the
same functions the CLI calls, so there is exactly one implementation of the
portability logic. Both are slow, whole-database operations; there is no
background-job infrastructure in this backend yet, so a request here blocks
for the duration of the export/import. Acceptable for a local, single-user
admin operation; would need revisiting before this became a hosted feature
(which is explicitly not the product this project is -- see CLAUDE.md's
"Explicitly not doing" list).
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from scripts.export_friend import export_friend
from scripts.import_friend import import_friend

router = APIRouter(prefix="/api/friend", tags=["friend-data"])
MAX_IMPORT_ARCHIVE_BYTES = 100 * 1024 * 1024


@router.post("/export")
async def export_friend_endpoint(
    background_tasks: BackgroundTasks, skip_neo4j: bool = False
):
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as handle:
        out_path = Path(handle.name)

    try:
        await export_friend(out_path, skip_neo4j=skip_neo4j)
    except Exception as exc:
        out_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    # Delete only after Starlette has finished streaming. Relying on generic
    # /tmp cleanup leaks one archive per export on long-lived hosts.
    background_tasks.add_task(out_path.unlink, missing_ok=True)
    return FileResponse(
        out_path,
        media_type="application/gzip",
        filename="friend_export.tar.gz",
    )


@router.post("/import")
async def import_friend_endpoint(
    file: UploadFile = File(...),
    force: bool = Form(default=False),
    skip_neo4j: bool = Form(default=False),
):
    if not force:
        raise HTTPException(
            status_code=400,
            detail=(
                "import is destructive (TRUNCATEs the Postgres tables and can "
                "overwrite local identity/state files) -- pass force=true to confirm."
            ),
        )

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as handle:
        archive_path = Path(handle.name)
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_IMPORT_ARCHIVE_BYTES:
                archive_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail="Import archive exceeds the 100 MiB limit",
                )
            handle.write(chunk)

    try:
        await import_friend(archive_path, force=force, skip_neo4j=skip_neo4j)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc
    finally:
        archive_path.unlink(missing_ok=True)

    return {"status": "imported"}
