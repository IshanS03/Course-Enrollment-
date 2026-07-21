from pydantic import BaseModel, Field, ConfigDict  # type: ignore[import]
from typing import Literal
from datetime import datetime

Status = Literal["Enrolled", "Waitlisted", "Dropped", "Completed"]

class Enrollment(BaseModel):

    name: str | None = Field(default = None, min_length = 5, max_length = 75)
    student_id: str = Field(pattern =r"^TKT-\d{5}$") # subject to change
    status: Status
    enrollment_at: datetime
    updated_at: datetime