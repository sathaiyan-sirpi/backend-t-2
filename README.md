# Advanced Querying for /devices

This project extends the existing FastAPI CRUD app with advanced querying capabilities on `GET /devices/`.

Supported query parameters:

- `category` (string) — exact match (applies only if `category` column exists on the model).
- `min_price` (float) — filters records where price >= `min_price`. If the model has no `price` column, the implementation falls back to `max_altitude` or `core_stability` when available.
- `max_price` (float) — filters records where price <= `max_price`.
- `search` (string) — case-insensitive partial match across text fields (`name`, `title`, `description`) that exist on the model.
- `sort_by` (string) — allowed values: `price`, `created_at`. `price` is mapped to a numeric column in the model (fallback to `max_altitude` or `core_stability`). If you supply an invalid value, the API returns HTTP 422 with `{"detail": "Invalid sort_by field."}`.
- `order` (string) — `asc` or `desc`. Default is `desc`.
- `skip` (int) — pagination offset (>= 0).
- `limit` (int) — pagination limit (0 <= limit <= 100). Maximum allowed is 100.

Response format (JSON):

{
  "total": <int>,
  "skip": <int>,
  "limit": <int>,
  "items": [ ... devices ... ]
}

Notes and behavior:

- Execution order: filtering -> search -> sorting -> pagination.
- `total` is the count after applying filters and search but before pagination.
- Search is executed in SQL using `ILIKE`/`LIKE` (SQLAlchemy `.ilike`) — rows are not loaded into Python for filtering.
- Sorting only allows approved fields mapped to safe columns in code to prevent SQL injection.
- If a requested filter field (like `category` or `price`) does not exist on the model, the parameter is ignored.

Example requests:

- Filter only:
  - `GET /devices?category=fiction`
- Search only:
  - `GET /devices?search=dragon`
- Sort ascending:
  - `GET /devices?sort_by=price&order=asc`
- Sort descending:
  - `GET /devices?sort_by=price&order=desc`
- Combined query:
  - `GET /devices?category=fiction&search=dragon&sort_by=price&order=desc&skip=0&limit=10`
- Invalid sort field (example):
  - `GET /devices?sort_by=salary` => HTTP 422
- Limit greater than 100:
  - `GET /devices?limit=500` => Validation error (limit max is 100)

If you want `price` semantics tied to a specific column, consider adding a `price` column to the `AntigravityDevice` model.
