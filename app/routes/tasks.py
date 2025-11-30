from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.task import Task
from pydantic import BaseModel

router = APIRouter(prefix="/tasks", tags=["tasks"])

class TaskCreate(BaseModel):
    title: str
    description: str

class TaskResponse(BaseModel):
    id: int
    title: str
    description: str
    completed: bool

    class Config:
        from_attributes = True

@router.post("/", response_model=TaskResponse)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    db_task = Task(**task.dict(), owner_id=1)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@router.get("/", response_model=list[TaskResponse])
def get_tasks(db: Session = Depends(get_db)):
    return db.query(Task). all()

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.put("/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, task: TaskCreate, db: Session = Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db_task.title = task.title
    db_task.description = task.description
    db.commit()
    return db_task

@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(db_task)
    db.commit()
    return {"message": "Task deleted"}
