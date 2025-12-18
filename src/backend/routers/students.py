"""
Student management endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from typing import Dict, Any, Optional
import os
from pathlib import Path
import uuid
import hashlib

from ..database import db, teachers_collection

router = APIRouter(
    prefix="/students",
    tags=["students"]
)

# Get the uploads directory path
UPLOAD_DIR = Path(__file__).parent.parent.parent / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Collection for student data
students_collection = db['students']

# Allowed image file extensions
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif'}

def is_allowed_file(filename: str) -> bool:
    """Check if the file extension is allowed"""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

@router.post("/upload-picture")
async def upload_student_picture(
    email: str = Query(..., description="Student email address"),
    picture: UploadFile = File(...),
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Upload a student picture - requires teacher authentication"""
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required for this action")
    
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")
    
    # Validate file type
    if not is_allowed_file(picture.filename):
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Only JPG, JPEG, PNG, and GIF files are allowed."
        )
    
    # Generate a unique filename to avoid conflicts
    # Use hash of email to create a safe filename component
    file_extension = Path(picture.filename).suffix.lower()
    email_hash = hashlib.md5(email.encode()).hexdigest()[:12]
    unique_filename = f"student_{email_hash}_{uuid.uuid4().hex[:8]}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename
    
    # Save the file
    try:
        contents = await picture.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Update or create student record in database
    picture_url = f"/static/uploads/{unique_filename}"
    
    student = students_collection.find_one({"_id": email})
    
    # If student already has a picture, delete the old file
    if student and "picture_url" in student:
        old_filename = student["picture_url"].split("/")[-1]
        old_file_path = UPLOAD_DIR / old_filename
        if old_file_path.exists():
            try:
                old_file_path.unlink()
            except (FileNotFoundError, PermissionError) as e:
                # Log but don't fail if old file can't be deleted
                print(f"Warning: Could not delete old file {old_filename}: {e}")
    
    # Update student record
    students_collection.update_one(
        {"_id": email},
        {"$set": {"picture_url": picture_url, "picture_filename": unique_filename}},
        upsert=True
    )
    
    return {
        "message": f"Picture uploaded successfully for {email}",
        "picture_url": picture_url
    }

@router.get("/{email}/picture")
def get_student_picture(email: str) -> Dict[str, Any]:
    """Get student picture URL"""
    student = students_collection.find_one({"_id": email})
    
    if not student or "picture_url" not in student:
        raise HTTPException(status_code=404, detail="Student picture not found")
    
    return {
        "email": email,
        "picture_url": student["picture_url"]
    }

@router.get("")
@router.get("/")
def get_all_students() -> Dict[str, Any]:
    """Get all students with their picture information"""
    students = {}
    for student in students_collection.find():
        email = student.pop('_id')
        students[email] = student
    
    return students
