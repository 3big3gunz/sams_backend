import base64
import csv
import io
import json
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import engine, SessionLocal, init_db, User, Department, Course, AttendanceSession, AttendanceRecord
from auth import verify_password, hash_password, create_access_token, decode_access_token
from schemas import (
    Token, UserCreate, UserOut, UserUpdate,
    DepartmentCreate, DepartmentOut,
    CourseCreate, CourseOut,
    AttendanceSessionCreate, AttendanceSessionOut, AttendanceRecordOut,
    AttendanceSubmission
)
from face_engine import FaceEngine

# Initialize Database tables
init_db()

# Initialize Face Engine
face_engine = FaceEngine()

app = FastAPI(title="Hybrid Attendance Management API", version="1.0.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# OAuth2 Password Bearer for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# Seed default admin user and demo department/course if database is empty
def seed_data(db: Session):
    if db.query(User).count() == 0:
        print("Seeding initial database...")
        # Create department
        dept = Department(name="Computer Science")
        db.add(dept)
        db.commit()
        db.refresh(dept)

        # Create Admin
        admin = User(
            name="System Admin",
            email="admin@attendance.com",
            role="admin",
            password_hash=hash_password("admin123"),
            department_id=dept.id
        )
        # Create Lecturer
        lecturer = User(
            name="Dr. John Doe",
            email="lecturer@attendance.com",
            role="lecturer",
            password_hash=hash_password("lecturer123"),
            department_id=dept.id
        )
        # Create Student
        student = User(
            name="Alice Smith",
            email="student@attendance.com",
            role="student",
            password_hash=hash_password("student123"),
            department_id=dept.id
        )
        db.add_all([admin, lecturer, student])
        db.commit()

        # Create Course
        course = Course(
            name="Introduction to AI",
            department_id=dept.id,
            lecturer_id=lecturer.id
        )
        db.add(course)
        db.commit()
        print("Database seeded successfully.")

# Run seeding
db = SessionLocal()
seed_data(db)
db.close()

# Helper: Get current active user from JWT token
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email: str = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# Helper: Require specific role
def check_role(user: User, allowed_roles: List[str]):
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: insufficient permissions"
        )

# ================= AUTH ENDPOINTS =================

@app.post("/api/auth/login", response_model=Token)
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # Note: OAuth2 uses 'username' field, we match it to email
    user = db.query(User).filter(User.email == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "name": user.name
    }

@app.get("/api/auth/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    # Add custom property for serialization
    current_user.has_reference_image = current_user.reference_image is not None
    return current_user

# ================= DEPARTMENT ENDPOINTS =================

@app.get("/api/departments", response_model=List[DepartmentOut])
def list_departments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Department).all()

@app.post("/api/departments", response_model=DepartmentOut)
def create_department(dept: DepartmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_role(current_user, ["admin"])
    existing = db.query(Department).filter(Department.name == dept.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Department already exists")
    db_dept = Department(name=dept.name)
    db.add(db_dept)
    db.commit()
    db.refresh(db_dept)
    return db_dept

@app.delete("/api/departments/{id}")
def delete_department(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_role(current_user, ["admin"])
    dept = db.query(Department).filter(Department.id == id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    db.delete(dept)
    db.commit()
    return {"message": "Department deleted successfully"}

# ================= COURSE ENDPOINTS =================

@app.get("/api/courses", response_model=List[CourseOut])
def list_courses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    courses = db.query(Course).all()
    out = []
    for c in courses:
        item = CourseOut(
            id=c.id,
            name=c.name,
            department_id=c.department_id,
            lecturer_id=c.lecturer_id,
            department_name=c.department.name if c.department else None,
            lecturer_name=c.lecturer.name if c.lecturer else None
        )
        out.append(item)
    return out

@app.post("/api/courses", response_model=CourseOut)
def create_course(course: CourseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_role(current_user, ["admin"])
    
    # Verify department exists
    dept = db.query(Department).filter(Department.id == course.department_id).first()
    if not dept:
        raise HTTPException(status_code=400, detail="Department not found")
        
    # Verify lecturer exists if assigned
    if course.lecturer_id:
        lecturer = db.query(User).filter(User.id == course.lecturer_id, User.role == "lecturer").first()
        if not lecturer:
            raise HTTPException(status_code=400, detail="Lecturer not found")
            
    db_course = Course(
        name=course.name,
        department_id=course.department_id,
        lecturer_id=course.lecturer_id
    )
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return CourseOut(
        id=db_course.id,
        name=db_course.name,
        department_id=db_course.department_id,
        lecturer_id=db_course.lecturer_id,
        department_name=db_course.department.name if db_course.department else None,
        lecturer_name=db_course.lecturer.name if db_course.lecturer else None
    )

@app.delete("/api/courses/{id}")
def delete_course(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_role(current_user, ["admin"])
    course = db.query(Course).filter(Course.id == id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)
    db.commit()
    return {"message": "Course deleted successfully"}

# ================= USER MANAGEMENT ENDPOINTS =================

@app.get("/api/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_role(current_user, ["admin", "lecturer"])
    return db.query(User).all()

@app.get("/api/users/lecturers", response_model=List[UserOut])
def list_lecturers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(User).filter(User.role == "lecturer").all()

@app.post("/api/users", response_model=UserOut)
def create_user(user: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_role(current_user, ["admin"])
    
    # Validate role
    if user.role not in ["admin", "lecturer", "student"]:
        raise HTTPException(status_code=400, detail="Invalid user role. Must be 'admin', 'lecturer', or 'student'")
        
    # Verify department exists if provided
    if user.department_id:
        dept = db.query(Department).filter(Department.id == user.department_id).first()
        if not dept:
            raise HTTPException(status_code=400, detail="Department not found")

    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_user = User(
        name=user.name,
        email=user.email,
        role=user.role,
        department_id=user.department_id,
        password_hash=hash_password(user.password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.delete("/api/users/{id}")
def delete_user(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_role(current_user, ["admin"])
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

# Set or update student's reference image for face recognition
@app.post("/api/users/{id}/reference-image")
def upload_reference_image(
    id: int, 
    image_base64: str = Form(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_role(current_user, ["admin", "lecturer"])
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Strip base64 headers if any
    b64_data = image_base64
    if "," in b64_data:
        b64_data = b64_data.split(",")[1]
    
    try:
        img_bytes = base64.b64decode(b64_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Base64 image data")
        
    embedding, err = face_engine.get_embedding(img_bytes)
    if err:
        raise HTTPException(status_code=400, detail=f"Face processing error: {err}")
    
    user.reference_image = image_base64
    user.face_embedding = json.dumps(embedding)
    db.commit()
    
    return {"message": "Reference image and embedding stored successfully"}

# ================= SESSION MANAGEMENT ENDPOINTS =================

@app.get("/api/sessions", response_model=List[AttendanceSessionOut])
def list_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sessions = db.query(AttendanceSession).all()
    out = []
    for s in sessions:
        out.append(AttendanceSessionOut(
            id=s.id,
            course_id=s.course_id,
            course_name=s.course.name if s.course else None,
            start_time=s.start_time,
            end_time=s.end_time,
            status=s.status
        ))
    return out

@app.post("/api/sessions", response_model=AttendanceSessionOut)
def create_session(session: AttendanceSessionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_role(current_user, ["admin", "lecturer"])
    
    # Verify course exists
    course = db.query(Course).filter(Course.id == session.course_id).first()
    if not course:
        raise HTTPException(status_code=400, detail="Course not found")
        
    # Close any other active session for this course
    active_sessions = db.query(AttendanceSession).filter(
        AttendanceSession.course_id == session.course_id,
        AttendanceSession.status == "active"
    ).all()
    for s in active_sessions:
        s.status = "closed"
        import datetime
        s.end_time = datetime.datetime.utcnow()
    
    db_session = AttendanceSession(
        course_id=session.course_id,
        status="active"
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    
    return AttendanceSessionOut(
        id=db_session.id,
        course_id=db_session.course_id,
        course_name=db_session.course.name if db_session.course else None,
        start_time=db_session.start_time,
        status=db_session.status
    )

@app.put("/api/sessions/{id}/close", response_model=AttendanceSessionOut)
def close_session(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_role(current_user, ["admin", "lecturer"])
    session = db.query(AttendanceSession).filter(AttendanceSession.id == id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    import datetime
    session.status = "closed"
    session.end_time = datetime.datetime.utcnow()
    db.commit()
    
    return AttendanceSessionOut(
        id=session.id,
        course_id=session.course_id,
        course_name=session.course.name if session.course else None,
        start_time=session.start_time,
        end_time=session.end_time,
        status=session.status
    )

# ================= ATTENDANCE FLOW ENDPOINTS =================

@app.post("/api/attendance/submit")
def submit_attendance(submission: AttendanceSubmission, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_role(current_user, ["student"])
    
    # Check if session is active
    session = db.query(AttendanceSession).filter(
        AttendanceSession.id == submission.session_id,
        AttendanceSession.status == "active"
    ).first()
    if not session:
        raise HTTPException(status_code=400, detail="Attendance session is closed or invalid")
        
    # Check if student has a reference image enrolled
    if not current_user.face_embedding:
        raise HTTPException(status_code=400, detail="You do not have a reference photo registered. Contact admin.")
    
    # Extract live image bytes
    b64_data = submission.image_base64
    if "," in b64_data:
        b64_data = b64_data.split(",")[1]
    
    try:
        live_img_bytes = base64.b64decode(b64_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid live image format")
        
    # Extract embedding from live photo
    live_embedding, err = face_engine.get_embedding(live_img_bytes)
    if err:
        raise HTTPException(status_code=400, detail=f"Face recognition engine: {err}")
        
    # Compare with stored reference embedding
    ref_embedding = json.loads(current_user.face_embedding)
    similarity = face_engine.compare_embeddings(live_embedding, ref_embedding)
    
    # Similarity threshold (usually around 0.36 for SFace Cosine Matching in OpenCV)
    # Since match score ranges from -1.0 to 1.0, 0.36 is standard threshold for positive match.
    THRESHOLD = 0.36
    
    status_result = "present" if similarity >= THRESHOLD else "absent"
    
    # Check if a record already exists for this user in this session
    existing_record = db.query(AttendanceRecord).filter(
        AttendanceRecord.user_id == current_user.id,
        AttendanceRecord.session_id == session.id
    ).first()
    
    if existing_record:
        # Update existing record
        existing_record.status = status_result
        existing_record.similarity_score = similarity
        import datetime
        existing_record.timestamp = datetime.datetime.utcnow()
        db.commit()
        db.refresh(existing_record)
        record = existing_record
    else:
        # Create new record
        record = AttendanceRecord(
            user_id=current_user.id,
            session_id=session.id,
            status=status_result,
            similarity_score=similarity
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        
    return {
        "status": record.status,
        "similarity_score": similarity,
        "match": record.status == "present"
    }

@app.get("/api/attendance/records", response_model=List[AttendanceRecordOut])
def get_attendance_records(
    course_id: Optional[int] = None,
    student_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(AttendanceRecord)
    
    # If student, restrict records to their own
    if current_user.role == "student":
        query = query.filter(AttendanceRecord.user_id == current_user.id)
    elif student_id:
        query = query.filter(AttendanceRecord.user_id == student_id)
        
    if course_id:
        query = query.join(AttendanceSession).filter(AttendanceSession.course_id == course_id)
        
    records = query.all()
    out = []
    for r in records:
        out.append(AttendanceRecordOut(
            id=r.id,
            user_id=r.user_id,
            session_id=r.session_id,
            timestamp=r.timestamp,
            status=r.status,
            similarity_score=r.similarity_score,
            student_name=r.user.name if r.user else None,
            course_name=r.session.course.name if r.session and r.session.course else None
        ))
    return out

@app.get("/api/attendance/export")
def export_attendance_records(
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_role(current_user, ["admin", "lecturer"])
    
    query = db.query(AttendanceRecord)
    if course_id:
        query = query.join(AttendanceSession).filter(AttendanceSession.course_id == course_id)
        
    records = query.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Record ID", "Student Name", "Email", "Course Name", "Session ID", "Timestamp", "Status", "Similarity Score"])
    
    for r in records:
        writer.writerow([
            r.id,
            r.user.name if r.user else "",
            r.user.email if r.user else "",
            r.session.course.name if r.session and r.session.course else "",
            r.session_id,
            r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            r.status,
            f"{r.similarity_score:.4f}" if r.similarity_score is not None else "N/A"
        ])
        
    output.seek(0)
    
    headers = {
        'Content-Disposition': 'attachment; filename="attendance_report.csv"'
    }
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
