from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import engine, Base, SessionLocal
from backend import models

app = FastAPI()

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class DailyEntry(BaseModel):
    date: str
    weight: float | None = None
    glucose: float | None = None
    notes: str | None = None


@app.get("/")
def home():
    return {"message": "Nutrition Tracker API is running"}


@app.post("/entries")
def create_entry(entry: DailyEntry, db: Session = Depends(get_db)):
    db_entry = models.DailyEntry(
        date=entry.date,
        weight=entry.weight,
        glucose=entry.glucose,
        notes=entry.notes
    )

    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)

    return {"message": "Entry saved", "id": db_entry.id}