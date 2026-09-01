from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    UniqueConstraint
)
from sqlalchemy.orm import relationship

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    username = Column(
        String,
        nullable=False,
        unique=True,
        index=True
    )

    email = Column(
        String,
        nullable=False,
        unique=True,
        index=True
    )

    password_hash = Column(
        String,
        nullable=False
    )

    daily_entries = relationship(
        "DailyEntry",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    supplement_profiles = relationship(
        "SupplementProfile",
        back_populates="user",
        cascade="all, delete-orphan"
    )


class DailyEntry(Base):
    __tablename__ = "daily_entries"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    date = Column(
        String,
        nullable=False
    )

    weight = Column(
        Float,
        nullable=True
    )

    glucose = Column(
        Float,
        nullable=True
    )

    notes = Column(
        String,
        nullable=True
    )

    state_of_day = Column(
        String,
        nullable=True
    )

    user = relationship(
        "User",
        back_populates="daily_entries"
    )

    foods = relationship(
        "FoodEntry",
        back_populates="day",
        cascade="all, delete-orphan"
    )

    liquids = relationship(
        "LiquidEntry",
        back_populates="day",
        cascade="all, delete-orphan"
    )

    supplements = relationship(
        "SupplementEntry",
        back_populates="day",
        cascade="all, delete-orphan"
    )

    activities = relationship(
        "ActivityEntry",
        back_populates="day",
        cascade="all, delete-orphan"
    )

    measurements = relationship(
        "MeasurementEntry",
        back_populates="day",
        cascade="all, delete-orphan"
    )


class FoodEntry(Base):
    __tablename__ = "food_entries"

    id = Column(
        Integer,
        primary_key=True
    )

    daily_entry_id = Column(
        Integer,
        ForeignKey("daily_entries.id"),
        nullable=False
    )

    meal_type = Column(
        String,
        nullable=False
    )

    food_name = Column(
        String,
        nullable=False
    )

    quantity = Column(
        String,
        nullable=True
    )

    calories = Column(
        Float,
        nullable=True
    )

    protein = Column(
        Float,
        nullable=True
    )

    day = relationship(
        "DailyEntry",
        back_populates="foods"
    )


class LiquidEntry(Base):
    __tablename__ = "liquid_entries"

    id = Column(
        Integer,
        primary_key=True
    )

    daily_entry_id = Column(
        Integer,
        ForeignKey("daily_entries.id"),
        nullable=False
    )

    drink_name = Column(
        String,
        nullable=False
    )

    amount_ml = Column(
        Float,
        nullable=True
    )

    calories = Column(
        Float,
        nullable=True
    )

    day = relationship(
        "DailyEntry",
        back_populates="liquids"
    )


class SupplementEntry(Base):
    __tablename__ = "supplement_entries"

    id = Column(
        Integer,
        primary_key=True
    )

    daily_entry_id = Column(
        Integer,
        ForeignKey("daily_entries.id"),
        nullable=False
    )

    supplement_name = Column(
        String,
        nullable=False
    )

    time_of_day = Column(
        String,
        nullable=True
    )

    quantity = Column(
        String,
        nullable=True
    )

    day = relationship(
        "DailyEntry",
        back_populates="supplements"
    )


class SupplementProfile(Base):
    __tablename__ = "supplement_profiles"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "supplement_name",
            name="uq_supplement_profiles_user_name"
        ),
    )

    id = Column(
        Integer,
        primary_key=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    supplement_name = Column(
        String,
        nullable=False
    )

    purpose = Column(
        String,
        nullable=True
    )

    usual_dose = Column(
        String,
        nullable=True
    )

    usual_timing = Column(
        String,
        nullable=True
    )

    notes = Column(
        String,
        nullable=True
    )

    user = relationship(
        "User",
        back_populates="supplement_profiles"
    )


class ActivityEntry(Base):
    __tablename__ = "activity_entries"

    id = Column(
        Integer,
        primary_key=True
    )

    daily_entry_id = Column(
        Integer,
        ForeignKey("daily_entries.id"),
        nullable=False
    )

    activity_type = Column(
        String,
        nullable=False,
        default="Walking"
    )

    distance_km = Column(
        Float,
        nullable=True
    )

    calories_burned = Column(
        Float,
        nullable=True
    )

    day = relationship(
        "DailyEntry",
        back_populates="activities"
    )


class MeasurementEntry(Base):
    __tablename__ = "measurement_entries"

    id = Column(
        Integer,
        primary_key=True
    )

    daily_entry_id = Column(
        Integer,
        ForeignKey("daily_entries.id"),
        nullable=False
    )

    systolic = Column(
        Float,
        nullable=True
    )

    diastolic = Column(
        Float,
        nullable=True
    )

    day = relationship(
        "DailyEntry",
        back_populates="measurements"
    )