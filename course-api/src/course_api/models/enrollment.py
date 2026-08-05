from pydantic import BaseModel, Field, ConfigDict
from typing import Literal
from datetime import datetime

Status = Literal["enrolled", "waitlisted", "dropped", "completed", "late_drop"]

# Student ids look like "S-12345": letter prefix, dash, digits.
STUDENT_ID_PATTERN = r"^S-\d{4,6}$"


class Enrollment(BaseModel):

    ConfigDict(extra="forbid")
    id: int
    course_id: int
    student_id: str = Field(pattern=STUDENT_ID_PATTERN)
    student_name: str = Field(min_length=1, max_length=100)
    status: Status
    grade: str | None = Field(default=None, max_length=2)
    waitlist_position: int | None = Field(default=None, ge=1)
    enrolled_at: datetime
    updated_at: datetime

class EnrollmentCreate(BaseModel):

    ConfigDict(extra="forbid")
    course_id: int
    student_id: str = Field(pattern=STUDENT_ID_PATTERN)
    student_name: str = Field(min_length=2, max_length=100)


class EnrollmentUpdate(BaseModel):

    ConfigDict(extra="forbid")
    status: Status | None = None
    grade: str | None = Field(default=None, max_length=2)
