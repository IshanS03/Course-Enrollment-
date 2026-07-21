from pydantic import BaseModel, Field, ConfigDict  
from typing import Literal
from datetime import datetime

Semester = Literal["Fall 2026", "Spring 2027", "Fall 2027", "Spring 2028"]
Days = Literal["MWF", "TTH"]

class Course(BaseModel):

    title: str = Field(min_length = 5, max_length = 200)
    course_id: str = Field(pattern =r"^TKT-\d{5}$") # subject to change
    instuctor: str | None = Field(default = None, min_length = 1, max_length= 50) 
    capacity : int = Field(min_capacity = 10, max_capacity = 1000)
    count: int
    semester: Semester 
    start_time: int | None = Field(default = None, min_start = 8, max_start = 18)  
    end_time: int | None = Field(default = None, min_end = 9, max_end = 21)    
    created_at: datetime
    updated_at: datetime