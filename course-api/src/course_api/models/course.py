from pydantic import BaseModel, Field, ConfigDict
from typing import Literal
from datetime import datetime

Semester = Literal["Fall 2026", "Spring 2027", "Fall 2027", "Spring 2028"]
Days = Literal["MWF", "TTH"]

# Course codes look like "CS-301" or "MATH-101": 2-4 uppercase letters, dash, three digits.
COURSE_CODE_PATTERN = r"^[A-Z]{2,4}-\d{3}$"


class Course(BaseModel):

    id: int
    course_code: str = Field(pattern=COURSE_CODE_PATTERN)
    title: str = Field(min_length=5, max_length=200)
    instructor: str | None = Field(default=None, min_length=1, max_length=100)
    capacity: int = Field(ge=0, le=1000)
    semester: Semester
    days: Days
    drop_deadline: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_time: int | None = Field(default=None, ge=8, le=18)
    end_time: int | None = Field(default=None, ge=9, le=21)
    created_at: datetime
    updated_at: datetime

class CourseCreate(BaseModel):
    """Schema for POST /courses. Server assigns id, time_stamps, *maybe course_code?"""

    model_config = ConfigDict(extra="forbid")

    course_code: str = Field(pattern=COURSE_CODE_PATTERN)
    title: str = Field(min_length=5, max_length=200)
    instructor: str | None = Field(default=None, min_length=1, max_length=100)
    capacity: int = Field(ge=0, le=1000)
    semester: Semester
    days: Days
    drop_deadline: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")  # ISO 8601 date string. ("2026-10-15")
    start_time: int | None = Field(default=None, ge=8, le=18)
    end_time: int | None = Field(default=None, ge=9, le=21)

class CourseUpdate(BaseModel):
    """Schema for PATCH /courses/<id>. All fields optional """

    model_config = ConfigDict(extra="forbid")

    instructor: str | None = Field(default=None, min_length=1, max_length=100)
    capacity: int | None = Field(default=None, ge=0, le=1000)
    semester: Semester | None = None
    days: Days | None = None
    start_time: int | None = Field(default=None, ge=8, le=18)
    end_time: int | None = Field(default=None, ge=9, le=21)

