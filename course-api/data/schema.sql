

CREATE TABLE IF NOT EXISTS courses (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code          TEXT    NOT NULL UNIQUE,               -- e.g. "CS-301"
    title                TEXT    NOT NULL,
    instructor           TEXT,
    semester             TEXT    NOT NULL,                       -- e.g. "Fall 2026"
    days                 TEXT    NOT NULL,
    start_time           INTEGER NOT NULL,
    end_time             INTEGER NOT NULL,
    capacity             INTEGER NOT NULL CHECK (capacity >= 0),

    -- AI enrichment columns should go here.

    created_at           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_courses_semester   ON courses(semester);
CREATE INDEX IF NOT EXISTS idx_courses_instructor ON courses(instructor);


CREATE TABLE IF NOT EXISTS enrollments (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id         INTEGER NOT NULL,
    student_id        TEXT    NOT NULL,
    student_name      TEXT    NOT NULL,
    enrolled_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    status            TEXT    NOT NULL DEFAULT 'enrolled'
                              CHECK (status IN ('enrolled', 'waitlisted', 'dropped',
                                                'completed', 'late_drop')),
    grade             TEXT,                                      -- null until course over
    waitlist_position INTEGER,                                   -- FIFO order; null unless waitlisted

    updated_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_enrollments_course       ON enrollments(course_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_course_status ON enrollments(course_id, status);
CREATE INDEX IF NOT EXISTS idx_enrollments_student      ON enrollments(student_id);

-- A student can't hold two active rows in the same course. Dropped/late_drop
-- rows are kept for auditing purposes and are excluded from this constraint via a
-- partial unique index over active statuses only.
CREATE UNIQUE INDEX IF NOT EXISTS uq_enrollment_active
    ON enrollments(course_id, student_id)
    WHERE status IN ('enrolled', 'waitlisted');
