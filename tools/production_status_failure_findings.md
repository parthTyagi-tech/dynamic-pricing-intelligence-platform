# Production recommendation status failure findings

Captured from Vercel function logs on 2026-08-27:

- POST `/api/recommendations/generate/<product>` returned HTTP 202.
- POST `/api/recommendations/process-task` returned HTTP 200, but the log message says: `Task exception was never retrieved`.
- GET `/api/recommendations/status/<recommendation>` returned HTTP 500 with `Unhandled application error Traceback (most recent call last):`.
- The visible log row truncates the traceback, so the exact exception line is not yet captured.
- The worker task is reaching the API, but its exception is being swallowed or logged asynchronously while the status serializer also errors.
