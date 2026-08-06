# Course Enrollment System

A Flask + SQLite backend for managing a course catalog and student enrollments.
A course never holds more `enrolled` students than its capacity, and waitlist
promotion happens atomically when a seat opens up. Course records are enriched on
the write path by Azure OpenAI, validated through Pydantic before being persisted.

---

## Install and Run

Install (from `course-api/`):

```bash
pip install -e ".[dev]"
```

Run (from `course-api/docker/`):

```bash
docker compose up
```

The service listens on `http://localhost:5000`. Compose initializes the schema and
seeds from `data/courses.json` before starting gunicorn.

Run locally without Docker, and run the tests (from `course-api/`):

```bash
flask --app course_api run
pytest
```

### Environment

Azure credentials are read from `.env` at the repository root via python-dotenv.
`.env` is gitignored and injected at runtime by compose, so the key never enters an
image layer.

```
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_API_KEY
AZURE_OPENAI_DEPLOYMENT
AZURE_OPENAI_API_VERSION
```

If any are missing, the service runs normally with every course saved at
`enrichment_status = "pending"`. This is what makes the tests runnable with no
Azure account.

---

## API

### Courses

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/courses` | List; filter by `instructor`, `semester`, `limit` |
| GET | `/courses/{id}` | Fetch one |
| POST | `/courses` | Create (runs enrichment) |
| PATCH | `/courses/{id}` | Update (re-runs enrichment when triggers change) |
| DELETE | `/courses/{id}` | Delete and cascade its enrollments |

### Enrollments

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/enrollments` | List; filter by `course_id`, `student_id`, `status`, `limit` |
| GET | `/enrollments/{id}` | Fetch one |
| POST | `/enrollments` | Enroll a student (auto-waitlists when full) |
| PATCH | `/enrollments/{id}` | Update status or grade |
| DELETE | `/enrollments/{id}` | Drop a student (soft delete; promotes from waitlist) |

### Health

`GET /live` confirms the process is serving. `GET /ready` runs `SELECT 1` against
the database, returning 503 when it is unreachable.

### Example

```bash
curl -X POST http://localhost:5000/courses \
  -H 'Content-Type: application/json' \
  -d '{"course_code":"CS-301","title":"Operating Systems","instructor":"Ada Lovelace",
       "capacity":30,"semester":"Fall 2026","days":"MWF","drop_deadline":"2026-12-01",
       "learning_objectives":"Students will learn process scheduling, virtual memory, and concurrency primitives."}'
```

### Error envelopes

| Status | Condition |
| --- | --- |
| 404 | `course_not_found`, `enrollment_not_found`, `route_not_found` |
| 405 | `method_not_allowed`, with allowed methods listed |
| 409 | `capacity_below_enrolled`, `conflict` |
| 422 | `validation_failed`, with field-by-field detail |
| 500 | `internal_server_error` — traceback to logs, never the response |

```json
{
  "error": "capacity_below_enrolled",
  "message": "cannot set capacity to 1: 2 students are already enrolled",
  "course_id": 4,
  "new_capacity": 1,
  "enrolled_count": 2
}
```

---

## Bonus Features

### Rate limiting

`flask-limiter` is wired once in `limiter.py` and applied in
`create_app()`. A global default of `200 per minute` per IP covers every route;


| Route | Limit |
| --- | --- |
| `POST /courses` | 10 per minute |
| `POST /enrollments` | 100 per minute |
| `POST /enrollments/bulk` | 100 per minute |

Course post requests should be significantly less than enrollments due to the professor:student ratio being imbalanced.

Write endpoints override global default with a tighter limit since they do more work per
request

### Bulk enrollment import

`POST /enrollments/bulk` accepts a JSON array of enrollments and inserts them
all-or-nothing. The whole array is validated in one pass via
`TypeAdapter(list[EnrollmentCreate])` before any write happens; a single bad item
returns `422` with that item's index and field errors, and nothing is inserted.

Valid batches run inside one `BEGIN IMMEDIATE`/`COMMIT`, reusing the same
capacity-check-then-insert logic as the single-enrollment path so waitlist positions come out correct even when a batch overflows one course's capacity partway through.

---

## Documented Decisions

### Concurrent enrollment into the last seat

The read-count-then-insert sequence runs inside a single `BEGIN IMMEDIATE`
transaction. `BEGIN IMMEDIATE` takes SQLite's write lock at the start of the
transaction rather than at first write, so two requests serialize instead of
interleaving.

Client A takes the lock, counts 29 against a capacity of 30, inserts, commits.
Client B blocks on the lock (up to `busy_timeout = 5000`), then reads the committed
count of 30 and is written as `waitlisted`. B can never read the stale pre-A count,
which is what would allow a 31st enrolled student.

Connections use `isolation_level = None` so the service layer controls exactly
where transactions begin and commit. Every service function rolls back on error.

### Enrollment beyond capacity

Success with a waitlist, not a soft error. `POST /enrollments` against a full
course returns `201` with `status: "waitlisted"` and a `waitlist_position`. The
request was valid and a record was created, so a 4xx would misrepresent it. The
caller reads `status` to distinguish the outcomes.

### Dropping after the drop deadline

Accepted, with a distinct `late_drop` status. Blocking leaves a student stuck in a
course they have left; accepting silently loses the fact that it was late. Both
`dropped` and `late_drop` free a seat and trigger promotion. `drop_deadline` is
nullable — a course without one can always be dropped normally.

### Deleting an enrollment

Soft delete when enrollment is active. `DELETE /enrollments/{id}` marks the row `dropped` or `late_drop` and
returns `200` with the updated record. Enrollment history is audit data.

If there is a delete on a non-active enrollment, it is deleted from the database permanently.  

Because the row survives, a plain unique constraint would block a student from ever
re-enrolling. A partial unique index covers active statuses only, so a student
holds at most one active row per course while historical `dropped` rows coexist:

```sql
CREATE UNIQUE INDEX uq_enrollment_active
    ON enrollments(course_id, student_id)
    WHERE status IN ('enrolled', 'waitlisted');
```

### Deleting a course with active enrollments

Cascade. The `course_id` foreign key is `ON DELETE CASCADE` with `PRAGMA
foreign_keys = ON` set per connection. Orphaned enrollments pointing at a missing
course would be unreadable, and there is no course left to hold history against.

### Reducing capacity below the enrolled count

Rejected with `409 capacity_below_enrolled`; the update rolls back. Silently
demoting enrolled students would pick losers among students who already hold seats
— a registrar's decision, not the system's. Raising capacity is safe to automate:
the service promotes from the waitlist in a loop until seats are filled, in the
same transaction as the capacity change.

### Waitlist ordering

FIFO by `waitlist_position`. On promotion the lowest position wins and everyone
behind shifts down by one, so positions stay contiguous from 1.

---

## AI Enrichment

### Model

`gpt-5.1` on Azure OpenAI, API version `2024-10-21`.

Enrichment is one small JSON object per course write, not a per-request hot path,
so cost scales with course creation rather than traffic. The task needs reliable
adherence to a fixed schema and restraint about facts not in the input — a
fabricated prerequisite in a course catalog is a real harm. Instruction-following
on both counts is worth more than the savings from a cheaper deployment.

### Configuration

| Parameter | Value | Reasoning |
| --- | --- | --- |
| `temperature` | `0.0` | Structured extraction, not creative writing. Same objectives should give the same blurb; low variance keeps output in-schema. |
| `max_completion_tokens` | `800` | Covers reasoning tokens plus visible JSON. Too low truncates mid-object, surfacing as a validation error and an avoidable `failed`. |
| `response_format` | `{"type": "json_object"}` | Constrains the response to parseable JSON at the API level, so conformance does not rest on prompt wording alone. |


### Grounding and validation

The model receives only the course code, title, adn learning objectives. Its response is
parsed through `CourseEnrichment`, which constrains `overview` to 50–1200
characters, requires exactly three `learning_outcomes`, restricts `target_audience`
to four `Literal` values, and bounds `confidence` to `0.0–1.0`. Only validated
output is persisted; raw model text is never stored.

### Responsible AI safeguards

1. **Scope-constraining system prompt.** The model must use only the provided
   objectives and is explicitly barred from asserting prerequisites, accreditation,
   credit hours, or career guarantees — claims a student could act on to their
   detriment.
2. **Enriched fields are marked AI-generated.** Every course response nests
   enrichment under an object carrying `ai_generated: true` and a `status`, so
   generated prose is always distinguishable from registrar-entered data.
3. **Refusals handled explicitly.** A `content_filter` finish reason or empty
   content raises `EnrichmentRefused` rather than persisting a blank blurb.
4. **No unnecessary PII.** Only course code and objectives are sent; student names
   and ids never enter a prompt.
5. **Confidence is surfaced.** The model's own score for how well the objectives
   supported the blurb is persisted and returned, so thin enrichment is visible.

### Graceful degradation

Any failure — timeout, rate limit, refusal, validation error — is logged with the
correlation id and returns `enrichment_status = "failed"` with null columns. The
course is still written and the endpoint still returns `201`. A course with no
objectives, or a service with no Azure client, resolves to `"pending"` instead:
there is nothing to ground a blurb on, and inventing one is what safeguard 1
forbids.

Enrichment runs before the INSERT, so a create stays a single write.

### Re-enrichment on update

A `PATCH` re-runs enrichment only when `learning_objectives`, `title`,
`instructor`, or `semester` actually changes value. Changing capacity or meeting
times spends no Azure call. The call is made before `BEGIN IMMEDIATE` — holding the
write lock across a network call would serialize every writer behind an external
dependency.

---

## Architecture

```
src/course_api/
├── __init__.py              create_app() factory, blueprint + limiter wiring
├── db.py                    connections, schema init, JSON seeding
├── enrich.py                Azure OpenAI client (injectable)
├── models/                  Pydantic boundary schemas
├── repository/              parameterized SQL, row → dict mapping
├── service/                 transactional business logic
└── api/
    ├── errors.py            DomainError hierarchy + handlers
    ├── middleware.py        correlation id, request logging
    └── blueprints/          HTTP routing only
```

Routes handle HTTP, the service layer owns transactions, the repository owns SQL.
Capacity logic lives in one transactional place below the HTTP layer, which is why
dropping a student and raising capacity can share `promote_next_waitlisted` without
either exceeding capacity. The Azure client is built once per app and passed into
the service layer as an argument, so tests inject a stub without patching globals.





