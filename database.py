import datetime
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DATABASE_URL = "sqlite:///./attendance.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    users = relationship("User", back_populates="department")
    courses = relationship("Course", back_populates="department")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, nullable=False)  # admin, lecturer, student
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    password_hash = Column(String, nullable=False)
    reference_image = Column(Text, nullable=True)  # Base64 string of reference face
    face_embedding = Column(Text, nullable=True)  # JSON array string representing 128d or 512d vector

    department = relationship("Department", back_populates="users")
    courses_taught = relationship("Course", back_populates="lecturer")
    attendance_records = relationship("AttendanceRecord", back_populates="user")

    @property
    def has_reference_image(self):
        return self.reference_image is not None


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    lecturer_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    department = relationship("Department", back_populates="courses")
    lecturer = relationship("User", back_populates="courses_taught")
    sessions = relationship("AttendanceSession", back_populates="course")

class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    start_time = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default="active", nullable=False)  # active, closed

    course = relationship("Course", back_populates="sessions")
    records = relationship("AttendanceRecord", back_populates="session")

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("attendance_sessions.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    status = Column(String, nullable=False)  # present, absent, review
    similarity_score = Column(Float, nullable=True)

    user = relationship("User", back_populates="attendance_records")
    session = relationship("AttendanceSession", back_populates="records")

def init_db():
    Base.metadata.create_all(bind=engine)
