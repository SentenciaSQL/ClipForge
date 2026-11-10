"""WebSocket endpoints for live job updates."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.database.models import ProcessingJob
from app.database.session import SessionLocal

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for connection in self.active:
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws/jobs")
async def jobs_websocket(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # Push a lightweight snapshot periodically; clients may also ping.
            db = SessionLocal()
            try:
                jobs = db.scalars(
                    select(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(20)
                ).all()
                payload = {
                    "type": "jobs_snapshot",
                    "jobs": [
                        {
                            "id": job.id,
                            "status": job.status,
                            "current_stage": job.current_stage,
                            "progress": job.progress,
                            "message": job.message,
                            "job_type": job.job_type,
                            "video_id": job.video_id,
                            "project_id": job.project_id,
                        }
                        for job in jobs
                    ],
                }
            finally:
                db.close()
            await websocket.send_json(payload)
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=2.0)
            except asyncio.TimeoutError:
                continue
    except WebSocketDisconnect:
        manager.disconnect(websocket)
