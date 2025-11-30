from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import shutil
from datetime import datetime
import hashlib
from pathlib import Path

from ..database import get_db
from ..models import FileTransfer
from ..schemas import FileTransferResponse

router = APIRouter(prefix="/files", tags=["File Transfer"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 100 * 1024 * 1024

def calculate_checksum(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

@router.post("/upload", response_model=FileTransferResponse, status_code=201)
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large. Max: {MAX_FILE_SIZE/1024/1024}MB")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = UPLOAD_DIR / safe_filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        checksum = calculate_checksum(str(file_path))
        
        file_transfer = FileTransfer(
            filename=file.filename,
            stored_filename=safe_filename,
            file_path=str(file_path),
            file_size=file_size,
            checksum=checksum,
            upload_date=datetime.now(),
            status="completed"
        )
        
        db.add(file_transfer)
        db.commit()
        db.refresh(file_transfer)
        return file_transfer
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/", response_model=List[FileTransferResponse])
async def list_files(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(FileTransfer).offset(skip).limit(limit).all()

@router.get("/{file_id}", response_model=FileTransferResponse)
async def get_file_metadata(file_id: int, db: Session = Depends(get_db)):
    file_record = db.query(FileTransfer).filter(FileTransfer.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    return file_record

@router.get("/{file_id}/download")
async def download_file(file_id: int, db: Session = Depends(get_db)):
    file_record = db.query(FileTransfer).filter(FileTransfer.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = Path(file_record.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    current_checksum = calculate_checksum(str(file_path))
    if current_checksum != file_record.checksum:
        raise HTTPException(status_code=500, detail="File integrity check failed")
    
    return FileResponse(path=file_path, filename=file_record.filename, media_type='application/octet-stream')

@router.delete("/{file_id}")
async def delete_file(file_id: int, db: Session = Depends(get_db)):
    file_record = db.query(FileTransfer).filter(FileTransfer.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = Path(file_record.file_path)
    if file_path.exists():
        file_path.unlink()
    
    db.delete(file_record)
    db.commit()
    return {"message": f"File {file_record.filename} deleted successfully"}

@router.post("/{file_id}/verify")
async def verify_file_integrity(file_id: int, db: Session = Depends(get_db)):
    file_record = db.query(FileTransfer).filter(FileTransfer.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = Path(file_record.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    current_checksum = calculate_checksum(str(file_path))
    is_valid = current_checksum == file_record.checksum
    
    return {
        "file_id": file_id,
        "filename": file_record.filename,
        "is_valid": is_valid,
        "stored_checksum": file_record.checksum,
        "current_checksum": current_checksum
    }
