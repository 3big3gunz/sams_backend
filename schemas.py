# pyrefly: ignore [missing-import]
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import datetime

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    name: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

# User Schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: str  # admin, lecturer, student
    department_id: Optional[int] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    department_id: Optional[int] = None
    password: Optional[str] = None

class UserOut(UserBase):
    id: int
    has_reference_image: bool = False

    class Config:
        from_attributes = True

# Department Schemas
class DepartmentBase(BaseModel):
    name: str

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentOut(DepartmentBase):
    id: int

    class Config:
        from_attributes = True

# Course Schemas
class CourseBase(BaseModel):
    name: str
    department_id: int
    lecturer_id: Optional[int] = None

class CourseCreate(CourseBase):
    pass

class CourseOut(CourseBase):
    id: int
    department_name: Optional[str] = None
    lecturer_name: Optional[str] = None

    class Config:
        from_attributes = True

# Attendance Session Schemas
class AttendanceSessionBase(BaseModel):
    course_id: int

class AttendanceSessionCreate(AttendanceSessionBase):
    pass

class AttendanceSessionOut(BaseModel):
    id: int
    course_id: int
    course_name: Optional[str] = None
    start_time: datetime.datetime
    end_time: Optional[datetime.datetime] = None
    status: str

    class Config:
        from_attributes = True

# Attendance Record Schemas
class AttendanceRecordBase(BaseModel):
    user_id: int
    session_id: int
    status: str  # present, absent, review
    similarity_score: Optional[float] = None

class AttendanceRecordOut(AttendanceRecordBase):
    id: int
    timestamp: datetime.datetime
    student_name: Optional[str] = None
    course_name: Optional[str] = None

    class Config:
        from_attributes = True

class AttendanceSubmission(BaseModel):
    session_id: int
    image_base64: str  # Data URL or raw base64 string
