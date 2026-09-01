import base64

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from openai import OpenAI

from backend.database import engine, Base, SessionLocal
from backend import models


app = FastAPI()
client = OpenAI()

Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# ============================================================
# REQUEST MODELS
# ============================================================


class DailyEntryCreate(BaseModel):
    date: str
    weight: float | None = None
    glucose: float | None = None
    notes: str | None = None
    state_of_day: str | None = None


class FoodCreate(BaseModel):
    meal_type: str
    food_name: str
    quantity: str | None = None
    calories: float | None = None
    protein: float | None = None


class LiquidCreate(BaseModel):
    drink_name: str
    amount_ml: float | None = None
    calories: float | None = None


class SupplementCreate(BaseModel):
    supplement_name: str
    quantity: str | None = None
    time_of_day: str | None = None

    purpose: str | None = None
    usual_dose: str | None = None
    usual_timing: str | None = None
    profile_notes: str | None = None


class ActivityCreate(BaseModel):
    activity_type: str = "Walking"
    distance_km: float | None = None


class MeasurementCreate(BaseModel):
    systolic: float | None = None
    diastolic: float | None = None


class ReplaceJournalRequest(BaseModel):
    foods: list[FoodCreate] = Field(default_factory=list)
    liquids: list[LiquidCreate] = Field(default_factory=list)
    supplements: list[SupplementCreate] = Field(default_factory=list)
    activities: list[ActivityCreate] = Field(default_factory=list)


# ============================================================
# AI MODELS
# ============================================================


class AIParsedFood(BaseModel):
    meal_type: str
    food_name: str
    quantity: str | None = None
    calories: float | None = None
    protein: float | None = None


class AIParsedLiquid(BaseModel):
    drink_name: str
    amount_ml: float | None = None
    calories: float | None = None


class AIParsedSupplement(BaseModel):
    supplement_name: str

    quantity: str | None = None
    time_of_day: str | None = None

    purpose: str | None = None
    usual_dose: str | None = None
    usual_timing: str | None = None
    profile_notes: str | None = None


class AIParsedActivity(BaseModel):
    activity_type: str
    distance_km: float | None = None


class AIParsedJournal(BaseModel):
    foods: list[AIParsedFood]
    liquids: list[AIParsedLiquid]
    supplements: list[AIParsedSupplement]
    activities: list[AIParsedActivity]

    verdict: str


# ============================================================
# AI PROMPT
# ============================================================


AI_SYSTEM_PROMPT = (
    "You analyze a personal nutrition and supplement journal. "

    "The user may provide Romanian natural-language text, "
    "one or more photographs, or both. "

    "Treat the text and ALL photographs as parts of ONE daily journal. "

    "Text may contain context unavailable from photographs: "
    "meal type, quantity consumed, brands, preparation method, "
    "how much of the visible portion was eaten and timing. "

    "Use text to improve the visual analysis. "

    "If text and a photograph clearly describe the same item, "
    "DO NOT count the item twice. "

    "Photographs may represent different meals, snacks and drinks "
    "from the same day. "

    "Only include items actually mentioned by the user or reasonably "
    "visible in photographs. Never create placeholder objects. "

    "For every food item, estimate calories in kcal and protein in grams "
    "for the quantity actually consumed or visually estimated. "

    "For drinks, estimate calories when applicable. "
    "Water, unsweetened tea and plain black coffee normally have "
    "zero or negligible calories. "

    "Use realistic typical nutritional values when exact brand "
    "information is unavailable. "

    "When estimating from photographs, be conservative. "
    "Do not pretend to know invisible ingredients. "

    "If oil, sauces, dressings or other ingredients are uncertain, "
    "use a reasonable conservative estimate. "

    "Nutrition values are estimates, not laboratory measurements. "

    "Treat kefir, yogurt, soup and similar products according to context. "
    "If consumed as food, put them in foods rather than liquids. "

    "Use Romanian meal names when possible: "
    "mic dejun, pranz, cina, gustare. "

    "If meal context cannot be determined, use 'masa'. "

    "Do not invent activities or distances. "

    "SUPPLEMENTS REQUIRE PARTICULAR CARE. "

    "For every supplement actually mentioned as taken today, "
    "create one supplement object. "

    "IMPORTANT: if the same supplement is mentioned more than once "
    "because the user describes both today's administration and its "
    "permanent profile, combine all information into ONE supplement object. "

    "Do not create two objects for the same supplement unless the user "
    "clearly states that they took separate doses at different times. "

    "Separate today's administration from the permanent supplement profile. "

    "quantity means the amount actually taken today, for example "
    "'1 capsula', '2 comprimate', '1 plic'. "

    "time_of_day means when it was actually taken today. "

    "purpose means the user's own stated reason or purpose for taking it. "
    "Do NOT invent a medical purpose from your own knowledge. "
    "If the user does not state the purpose, return null. "

    "usual_dose means a habitual dose explicitly stated by the user. "
    "Do not assume one. "

    "usual_timing means habitual timing explicitly stated by the user, "
    "such as 'de obicei dupa cina'. "

    "profile_notes contains durable information explicitly supplied "
    "by the user about that supplement. "

    "If the user only says they took a supplement today, "
    "leave unknown profile fields null rather than guessing. "

    "If multiple different supplements are mentioned together, "
    "return them as separate supplement objects. "

    "Also create a short daily nutrition verdict in Romanian, "
    "normally 2 to 4 sentences. "

    "The verdict should be practical, friendly and factual. "
    "Comment only on information supported by the food, drinks "
    "and physical activity journal. "

    "Do not diagnose medical conditions. "
    "Do not analyze symptoms or health complaints. "

    "The separate 'state of the day' field is not provided to you "
    "and must not be inferred."
)


# ============================================================
# HELPERS
# ============================================================


def get_day_or_404(day_id: int, db: Session):
    day = (
        db.query(models.DailyEntry)
        .filter(models.DailyEntry.id == day_id)
        .first()
    )

    if not day:
        raise HTTPException(
            status_code=404,
            detail="Day not found"
        )

    return day


def calculate_day_summary(day):
    food_calories = sum(
        food.calories or 0
        for food in day.foods
    )

    liquid_calories = sum(
        liquid.calories or 0
        for liquid in day.liquids
    )

    intake_calories = (
        food_calories +
        liquid_calories
    )

    total_protein = sum(
        food.protein or 0
        for food in day.foods
    )

    total_liquids_ml = sum(
        liquid.amount_ml or 0
        for liquid in day.liquids
    )

    activity_calories = sum(
        activity.calories_burned or 0
        for activity in day.activities
    )

    after_activity = (
        intake_calories -
        activity_calories
    )

    return {
        "food_calories": round(food_calories, 1),
        "liquid_calories": round(liquid_calories, 1),
        "calories": round(intake_calories, 1),
        "protein": round(total_protein, 1),
        "liquids_ml": round(total_liquids_ml, 0),
        "activity_calories": round(activity_calories, 1),
        "after_activity": round(after_activity, 1)
    }


def upsert_supplement_profile(
    db: Session,
    supplement: SupplementCreate
):
    name = supplement.supplement_name.strip()

    if not name:
        return

    profile = (
        db.query(models.SupplementProfile)
        .filter(
            func.lower(
                models.SupplementProfile.supplement_name
            ) == name.lower()
        )
        .first()
    )

    if profile is None:
        profile = models.SupplementProfile(
            supplement_name=name
        )

        db.add(profile)

        # Important:
        # Make the newly created profile visible inside the same
        # transaction before another supplement can look it up.
        db.flush()

    if supplement.purpose:
        profile.purpose = supplement.purpose

    if supplement.usual_dose:
        profile.usual_dose = supplement.usual_dose

    if supplement.usual_timing:
        profile.usual_timing = supplement.usual_timing

    if supplement.profile_notes:
        profile.notes = supplement.profile_notes


def merge_duplicate_supplements(supplements):
    """
    AI may occasionally return the same supplement more than once
    when today's dose and permanent profile are described separately.

    For one daily journal we merge those fragments into one object.

    Example:
        Curalin -> today's dose
        Curalin -> permanent profile

    becomes:
        one complete Curalin object.
    """

    merged = {}

    for supplement in supplements:
        name = supplement.supplement_name.strip()

        if not name:
            continue

        key = name.casefold()

        if key not in merged:
            merged[key] = SupplementCreate(
                supplement_name=name,
                quantity=supplement.quantity,
                time_of_day=supplement.time_of_day,
                purpose=supplement.purpose,
                usual_dose=supplement.usual_dose,
                usual_timing=supplement.usual_timing,
                profile_notes=supplement.profile_notes
            )

            continue

        existing = merged[key]

        if (
            not existing.quantity
            and supplement.quantity
        ):
            existing.quantity = supplement.quantity

        if (
            not existing.time_of_day
            and supplement.time_of_day
        ):
            existing.time_of_day = supplement.time_of_day

        if (
            not existing.purpose
            and supplement.purpose
        ):
            existing.purpose = supplement.purpose

        if (
            not existing.usual_dose
            and supplement.usual_dose
        ):
            existing.usual_dose = supplement.usual_dose

        if (
            not existing.usual_timing
            and supplement.usual_timing
        ):
            existing.usual_timing = supplement.usual_timing

        if supplement.profile_notes:
            if not existing.profile_notes:
                existing.profile_notes = (
                    supplement.profile_notes
                )

            elif (
                supplement.profile_notes
                not in existing.profile_notes
            ):
                existing.profile_notes += (
                    " | "
                    + supplement.profile_notes
                )

    return list(merged.values())


# ============================================================
# FRONTEND
# ============================================================


@app.get("/")
def home():
    return FileResponse("backend/index.html")


# ============================================================
# UNIFIED AI ANALYSIS
# ============================================================


@app.post("/ai/analyze")
async def analyze_journal(
    text: str = Form(""),
    images: list[UploadFile] | None = File(None)
):
    try:
        text = text.strip()
        images = images or []

        if not text and not images:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Provide journal text, "
                    "at least one image, or both."
                )
            )

        if len(images) > 12:
            raise HTTPException(
                status_code=400,
                detail="Maximum 12 images per analysis."
            )

        user_content = []

        if text:
            context_text = (
                "This is the user's journal text. "
                "Use it together with any attached photographs:\n\n"
                + text
            )
        else:
            context_text = (
                "The user supplied photographs "
                "without additional text. "
                "Analyze all photographs as parts "
                "of the same daily journal."
            )

        user_content.append(
            {
                "type": "input_text",
                "text": context_text
            }
        )

        filenames = []

        for image in images:
            if not image.content_type:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unknown image type "
                        f"for {image.filename}."
                    )
                )

            if not image.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{image.filename} "
                        f"is not an image."
                    )
                )

            image_bytes = await image.read()

            if len(image_bytes) > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{image.filename} "
                        f"is larger than 10 MB."
                    )
                )

            encoded_image = base64.b64encode(
                image_bytes
            ).decode("utf-8")

            data_url = (
                f"data:{image.content_type};base64,"
                f"{encoded_image}"
            )

            user_content.append(
                {
                    "type": "input_image",
                    "image_url": data_url,
                    "detail": "auto"
                }
            )

            filenames.append(
                image.filename
            )

        response = client.responses.parse(
            model="gpt-5-nano",
            input=[
                {
                    "role": "system",
                    "content": AI_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            text_format=AIParsedJournal
        )

        parsed = response.output_parsed

        if parsed is None:
            raise HTTPException(
                status_code=500,
                detail=(
                    "AI did not return "
                    "structured data."
                )
            )

        # ----------------------------------------------------
        # SAFETY NET:
        # Merge duplicate fragments of the same supplement
        # before they ever reach the browser preview.
        # ----------------------------------------------------

        merged_supplements = (
            merge_duplicate_supplements(
                parsed.supplements
            )
        )

        parsed.supplements = [
            AIParsedSupplement(
                supplement_name=item.supplement_name,
                quantity=item.quantity,
                time_of_day=item.time_of_day,
                purpose=item.purpose,
                usual_dose=item.usual_dose,
                usual_timing=item.usual_timing,
                profile_notes=item.profile_notes
            )
            for item in merged_supplements
        ]

        return {
            "text_used": bool(text),
            "image_count": len(filenames),
            "filenames": filenames,
            "interpreted": parsed.model_dump()
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


# ============================================================
# DAILY ENTRIES
# ============================================================


@app.get("/entries")
def get_entries(
    db: Session = Depends(get_db)
):
    entries = (
        db.query(models.DailyEntry)
        .order_by(models.DailyEntry.date.desc())
        .all()
    )

    result = []

    for entry in entries:
        result.append(
            {
                "id": entry.id,
                "date": entry.date,
                "weight": entry.weight,
                "glucose": entry.glucose,
                "notes": entry.notes,
                "state_of_day": entry.state_of_day,
                "summary": calculate_day_summary(
                    entry
                )
            }
        )

    return result


@app.post("/entries")
def create_entry(
    entry: DailyEntryCreate,
    db: Session = Depends(get_db)
):
    existing = (
        db.query(models.DailyEntry)
        .filter(
            models.DailyEntry.date
            == entry.date
        )
        .first()
    )

    if existing:
        existing.weight = entry.weight
        existing.glucose = entry.glucose
        existing.notes = entry.notes
        existing.state_of_day = (
            entry.state_of_day
        )

        db.commit()
        db.refresh(existing)

        return {
            "message": "Day updated",
            "id": existing.id
        }

    db_entry = models.DailyEntry(
        date=entry.date,
        weight=entry.weight,
        glucose=entry.glucose,
        notes=entry.notes,
        state_of_day=entry.state_of_day
    )

    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)

    return {
        "message": "Day created",
        "id": db_entry.id
    }


# ============================================================
# REPLACE COMPLETE JOURNAL
# ============================================================


@app.post("/days/{day_id}/replace-journal")
def replace_journal(
    day_id: int,
    journal: ReplaceJournalRequest,
    db: Session = Depends(get_db)
):
    day = get_day_or_404(
        day_id,
        db
    )

    try:
        # ----------------------------------------------------
        # Delete today's old journal rows.
        # The DailyEntry itself is preserved.
        # ----------------------------------------------------

        db.query(
            models.FoodEntry
        ).filter(
            models.FoodEntry.daily_entry_id
            == day_id
        ).delete(
            synchronize_session=False
        )

        db.query(
            models.LiquidEntry
        ).filter(
            models.LiquidEntry.daily_entry_id
            == day_id
        ).delete(
            synchronize_session=False
        )

        db.query(
            models.SupplementEntry
        ).filter(
            models.SupplementEntry.daily_entry_id
            == day_id
        ).delete(
            synchronize_session=False
        )

        db.query(
            models.ActivityEntry
        ).filter(
            models.ActivityEntry.daily_entry_id
            == day_id
        ).delete(
            synchronize_session=False
        )

        # ----------------------------------------------------
        # Foods
        # ----------------------------------------------------

        for food in journal.foods:
            db.add(
                models.FoodEntry(
                    daily_entry_id=day_id,
                    meal_type=food.meal_type,
                    food_name=food.food_name,
                    quantity=food.quantity,
                    calories=food.calories,
                    protein=food.protein
                )
            )

        # ----------------------------------------------------
        # Liquids
        # ----------------------------------------------------

        for liquid in journal.liquids:
            db.add(
                models.LiquidEntry(
                    daily_entry_id=day_id,
                    drink_name=liquid.drink_name,
                    amount_ml=liquid.amount_ml,
                    calories=liquid.calories
                )
            )

        # ----------------------------------------------------
        # Supplements
        #
        # Second safety net:
        # even if duplicate supplement fragments somehow reach
        # the API, merge them before PostgreSQL.
        # ----------------------------------------------------

        merged_supplements = (
            merge_duplicate_supplements(
                journal.supplements
            )
        )

        for supplement in merged_supplements:
            db.add(
                models.SupplementEntry(
                    daily_entry_id=day_id,
                    supplement_name=(
                        supplement.supplement_name
                    ),
                    quantity=(
                        supplement.quantity
                    ),
                    time_of_day=(
                        supplement.time_of_day
                    )
                )
            )

            upsert_supplement_profile(
                db,
                supplement
            )

        # ----------------------------------------------------
        # Activities
        # ----------------------------------------------------

        for activity in journal.activities:
            calories_burned = None

            if (
                activity.distance_km is not None
                and day.weight is not None
            ):
                calories_burned = round(
                    0.5
                    * day.weight
                    * activity.distance_km,
                    1
                )

            db.add(
                models.ActivityEntry(
                    daily_entry_id=day_id,
                    activity_type=(
                        activity.activity_type
                    ),
                    distance_km=(
                        activity.distance_km
                    ),
                    calories_burned=(
                        calories_burned
                    )
                )
            )

        db.commit()

        return {
            "message": "Journal replaced",
            "day_id": day_id
        }

    except Exception as exc:
        db.rollback()

        # Print the real backend error as well,
        # so Docker logs are useful during development.
        print(
            "REPLACE JOURNAL ERROR:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


# ============================================================
# SUPPLEMENT HISTORY / CONTROL
# ============================================================


@app.get("/supplements/summary")
def supplement_summary(
    db: Session = Depends(get_db)
):
    profiles = (
        db.query(
            models.SupplementProfile
        )
        .all()
    )

    logged_rows = (
        db.query(
            models.SupplementEntry,
            models.DailyEntry
        )
        .join(
            models.DailyEntry,
            models.SupplementEntry.daily_entry_id
            == models.DailyEntry.id
        )
        .all()
    )

    history = {}

    for supplement_entry, day in logged_rows:
        name = (
            supplement_entry
            .supplement_name
            .strip()
        )

        if not name:
            continue

        key = name.casefold()

        if key not in history:
            history[key] = {
                "supplement_name": name,
                "dates": [],
                "events": []
            }

        history[key]["dates"].append(
            day.date
        )

        history[key]["events"].append(
            {
                "date": day.date,
                "quantity": (
                    supplement_entry.quantity
                ),
                "time_of_day": (
                    supplement_entry.time_of_day
                )
            }
        )

    profile_map = {
        profile.supplement_name
        .strip()
        .casefold(): profile

        for profile in profiles
    }

    all_keys = (
        set(history.keys())
        | set(profile_map.keys())
    )

    result = []

    for key in all_keys:
        hist = history.get(key)
        profile = profile_map.get(key)

        dates = (
            hist["dates"]
            if hist
            else []
        )

        events = (
            hist["events"]
            if hist
            else []
        )

        events = sorted(
            events,
            key=lambda item: item["date"]
        )

        last_event = (
            events[-1]
            if events
            else None
        )

        if profile:
            display_name = (
                profile.supplement_name
            )
        elif hist:
            display_name = (
                hist["supplement_name"]
            )
        else:
            display_name = key

        result.append(
            {
                "supplement_name":
                    display_name,

                "purpose":
                    profile.purpose
                    if profile
                    else None,

                "usual_dose":
                    profile.usual_dose
                    if profile
                    else None,

                "usual_timing":
                    profile.usual_timing
                    if profile
                    else None,

                "notes":
                    profile.notes
                    if profile
                    else None,

                "first_taken":
                    min(dates)
                    if dates
                    else None,

                "last_taken":
                    max(dates)
                    if dates
                    else None,

                "times_logged":
                    len(events),

                "last_quantity":
                    last_event["quantity"]
                    if last_event
                    else None,

                "last_timing":
                    last_event["time_of_day"]
                    if last_event
                    else None
            }
        )

    # Most recently taken supplements first.
    # Profiles never logged are placed last.
    result.sort(
        key=lambda item: (
            item["last_taken"]
            is not None,
            item["last_taken"] or ""
        ),
        reverse=True
    )

    return result


# ============================================================
# INDIVIDUAL ENDPOINTS
# ============================================================


@app.post("/days/{day_id}/foods")
def add_food(
    day_id: int,
    food: FoodCreate,
    db: Session = Depends(get_db)
):
    get_day_or_404(
        day_id,
        db
    )

    db_food = models.FoodEntry(
        daily_entry_id=day_id,
        meal_type=food.meal_type,
        food_name=food.food_name,
        quantity=food.quantity,
        calories=food.calories,
        protein=food.protein
    )

    db.add(db_food)
    db.commit()
    db.refresh(db_food)

    return {
        "message": "Food added",
        "id": db_food.id
    }


@app.post("/days/{day_id}/liquids")
def add_liquid(
    day_id: int,
    liquid: LiquidCreate,
    db: Session = Depends(get_db)
):
    get_day_or_404(
        day_id,
        db
    )

    db_liquid = models.LiquidEntry(
        daily_entry_id=day_id,
        drink_name=liquid.drink_name,
        amount_ml=liquid.amount_ml,
        calories=liquid.calories
    )

    db.add(db_liquid)
    db.commit()
    db.refresh(db_liquid)

    return {
        "message": "Liquid added",
        "id": db_liquid.id
    }


@app.post("/days/{day_id}/supplements")
def add_supplement(
    day_id: int,
    supplement: SupplementCreate,
    db: Session = Depends(get_db)
):
    get_day_or_404(
        day_id,
        db
    )

    try:
        db_supplement = (
            models.SupplementEntry(
                daily_entry_id=day_id,
                supplement_name=(
                    supplement.supplement_name
                ),
                quantity=(
                    supplement.quantity
                ),
                time_of_day=(
                    supplement.time_of_day
                )
            )
        )

        db.add(
            db_supplement
        )

        upsert_supplement_profile(
            db,
            supplement
        )

        db.commit()
        db.refresh(
            db_supplement
        )

        return {
            "message":
                "Supplement added",

            "id":
                db_supplement.id
        }

    except Exception as exc:
        db.rollback()

        print(
            "ADD SUPPLEMENT ERROR:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


@app.post("/days/{day_id}/activities")
def add_activity(
    day_id: int,
    activity: ActivityCreate,
    db: Session = Depends(get_db)
):
    day = get_day_or_404(
        day_id,
        db
    )

    calories_burned = None

    if (
        activity.distance_km is not None
        and day.weight is not None
    ):
        calories_burned = round(
            0.5
            * day.weight
            * activity.distance_km,
            1
        )

    db_activity = models.ActivityEntry(
        daily_entry_id=day_id,
        activity_type=(
            activity.activity_type
        ),
        distance_km=(
            activity.distance_km
        ),
        calories_burned=(
            calories_burned
        )
    )

    db.add(
        db_activity
    )

    db.commit()
    db.refresh(
        db_activity
    )

    return {
        "message": "Activity added",
        "id": db_activity.id,
        "estimated_calories":
            calories_burned
    }


@app.post("/days/{day_id}/measurements")
def add_measurement(
    day_id: int,
    measurement: MeasurementCreate,
    db: Session = Depends(get_db)
):
    get_day_or_404(
        day_id,
        db
    )

    db_measurement = (
        models.MeasurementEntry(
            daily_entry_id=day_id,
            systolic=measurement.systolic,
            diastolic=measurement.diastolic
        )
    )

    db.add(
        db_measurement
    )

    db.commit()
    db.refresh(
        db_measurement
    )

    return {
        "message": "Measurement added",
        "id": db_measurement.id
    }


# ============================================================
# FULL DAY
# ============================================================


@app.get("/days/{day_id}")
def get_full_day(
    day_id: int,
    db: Session = Depends(get_db)
):
    day = get_day_or_404(
        day_id,
        db
    )

    return {
        "id": day.id,
        "date": day.date,
        "weight": day.weight,
        "glucose": day.glucose,
        "notes": day.notes,
        "state_of_day": day.state_of_day,

        "summary":
            calculate_day_summary(
                day
            ),

        "foods": [
            {
                "id": food.id,
                "meal_type":
                    food.meal_type,
                "food_name":
                    food.food_name,
                "quantity":
                    food.quantity,
                "calories":
                    food.calories,
                "protein":
                    food.protein
            }
            for food in day.foods
        ],

        "liquids": [
            {
                "id": liquid.id,
                "drink_name":
                    liquid.drink_name,
                "amount_ml":
                    liquid.amount_ml,
                "calories":
                    liquid.calories
            }
            for liquid in day.liquids
        ],

        "supplements": [
            {
                "id":
                    supplement.id,

                "supplement_name":
                    supplement.supplement_name,

                "quantity":
                    supplement.quantity,

                "time_of_day":
                    supplement.time_of_day
            }
            for supplement
            in day.supplements
        ],

        "activities": [
            {
                "id":
                    activity.id,

                "activity_type":
                    activity.activity_type,

                "distance_km":
                    activity.distance_km,

                "calories_burned":
                    activity.calories_burned
            }
            for activity
            in day.activities
        ],

        "measurements": [
            {
                "id":
                    measurement.id,

                "systolic":
                    measurement.systolic,

                "diastolic":
                    measurement.diastolic
            }
            for measurement
            in day.measurements
        ]
    }