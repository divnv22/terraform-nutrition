from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class DailyEntry(BaseModel):
    date: str
    weight: float | None = None
    glucose: float | None = None
    notes: str | None = None


@app.get("/")
def home():
    return {"message": "Nutrition Tracker API is running"}


@app.post("/entries")
def create_entry(entry: DailyEntry):
    return {
        "message": "Entry received",
        "data": entry
    }