# API Reference (Phase 1)

Base URL: `http://127.0.0.1:8000`

Interactive docs: `/docs`

## Health

### `GET /api/health`

Returns service status, version, and hardware profile.

### `GET /api/hardware?refresh=false`

Returns detailed hardware detection results.

## Dashboard

### `GET /api/dashboard`

Aggregate counts, recent projects/jobs, hardware snapshot.

## Projects

### `POST /api/projects`

Body: `{ "name": string, "description"?: string }`

### `GET /api/projects`

### `GET /api/projects/{id}`

### `PATCH /api/projects/{id}`

### `DELETE /api/projects/{id}`

### `GET /api/projects/{id}/videos`

### `GET /api/projects/{id}/clips`

Phase 1 returns `[]` until clips are generated in later phases.

## Videos

### `POST /api/videos/import`

`multipart/form-data`:

- `file` (required)
- `project_id` (optional)
- `project_name` (optional; used when creating a new project)

Copies the file into `workspace/originals/{project_id}/` and extracts FFprobe metadata.

### `GET /api/videos?project_id=`

### `GET /api/videos/{id}`

### `GET /api/videos/{id}/metadata`

### `POST /api/videos/{id}/metadata/refresh`

### `DELETE /api/videos/{id}`

### `POST /api/videos/{id}/analyze`

Creates a queued `ProcessingJob` with pipeline stage placeholders. Stage execution starts in Phase 2+.

## Jobs

### `GET /api/jobs`

### `GET /api/jobs/{id}`

## Settings

### `GET /api/settings`

### `PATCH /api/settings`

Persists overrides in SQLite `app_settings` (key `runtime`).

## WebSocket

### `WS /ws/jobs`

Sends periodic `jobs_snapshot` messages with recent job progress.

## Planned (later phases)

- `POST /api/videos/{id}/highlights`
- `POST /api/clips/{id}/render`
- `PATCH /api/clips/{id}`
- `POST /api/clips/export`
- Audio Studio:
  - `POST /api/clips/{id}/audio/import`
  - `GET /api/clips/{id}/audio`
  - `PATCH /api/clips/{id}/audio`
  - `DELETE /api/clips/{id}/audio/{track_id}`
  - `POST /api/clips/{id}/audio/preview`
  - `POST /api/clips/{id}/audio/render`
