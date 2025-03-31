from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/job_changes')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class JobChange(Base):
    __tablename__ = "job_changes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    company = Column(String)
    old_position = Column(String)
    new_position = Column(String)
    change_date = Column(DateTime)
    profile_url = Column(String)
    is_new = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    linkedin_url = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic Models
class JobChangeBase(BaseModel):
    name: str
    company: str
    old_position: Optional[str] = None
    new_position: str
    change_date: datetime
    profile_url: str

class JobChangeCreate(JobChangeBase):
    pass

class JobChange(JobChangeBase):
    id: int
    is_new: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class CompanyBase(BaseModel):
    name: str
    linkedin_url: str

class CompanyCreate(CompanyBase):
    pass

class Company(CompanyBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# FastAPI app
app = FastAPI(
    title="AI Job Change Tracker API",
    description="API for tracking job changes across companies",
    version="1.0.0"
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Routes
@app.get("/")
async def root():
    return {"message": "Welcome to AI Job Change Tracker API"}

@app.get("/job-changes/", response_model=List[JobChange])
def get_job_changes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    company: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """Get job changes with optional filtering"""
    query = db.query(JobChange)
    
    if company:
        query = query.filter(JobChange.company == company)
    if start_date:
        query = query.filter(JobChange.change_date >= start_date)
    if end_date:
        query = query.filter(JobChange.change_date <= end_date)
    
    return query.offset(skip).limit(limit).all()

@app.post("/job-changes/", response_model=JobChange)
def create_job_change(job_change: JobChangeCreate, db: Session = Depends(get_db)):
    """Create a new job change record"""
    db_job_change = JobChange(**job_change.dict())
    db.add(db_job_change)
    db.commit()
    db.refresh(db_job_change)
    return db_job_change

@app.get("/companies/", response_model=List[Company])
def get_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """Get companies with optional filtering"""
    query = db.query(Company)
    if active_only:
        query = query.filter(Company.is_active == True)
    return query.offset(skip).limit(limit).all()

@app.post("/companies/", response_model=Company)
def create_company(company: CompanyCreate, db: Session = Depends(get_db)):
    """Create a new company"""
    db_company = Company(**company.dict())
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company

@app.put("/companies/{company_id}/deactivate")
def deactivate_company(company_id: int, db: Session = Depends(get_db)):
    """Deactivate a company"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company.is_active = False
    db.commit()
    return {"message": "Company deactivated successfully"}

@app.get("/stats/")
def get_stats(
    company: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """Get statistics about job changes"""
    query = db.query(JobChange)
    
    if company:
        query = query.filter(JobChange.company == company)
    if start_date:
        query = query.filter(JobChange.change_date >= start_date)
    if end_date:
        query = query.filter(JobChange.change_date <= end_date)
    
    total_changes = query.count()
    unique_people = query.with_entities(JobChange.name).distinct().count()
    unique_companies = query.with_entities(JobChange.company).distinct().count()
    
    return {
        "total_changes": total_changes,
        "unique_people": unique_people,
        "unique_companies": unique_companies
    }

@app.get("/companies/{company_id}/changes/", response_model=List[JobChange])
def get_company_changes(
    company_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """Get job changes for a specific company"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    query = db.query(JobChange).filter(JobChange.company == company.name)
    
    if start_date:
        query = query.filter(JobChange.change_date >= start_date)
    if end_date:
        query = query.filter(JobChange.change_date <= end_date)
    
    return query.offset(skip).limit(limit).all()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
