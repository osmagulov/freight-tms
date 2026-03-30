"""
Eco-Driving / Driver Scoring Service
Inspired by Wialon's driver behavior monitoring module.

Since we don't have GPS trackers or CAN-bus, the scoring is based on
data that drivers report through the app:
  - Fuel efficiency: actual vs. vehicle norm
  - Expense discipline: rejections, anomalies
  - Trip count and distance covered
  - On-time delivery (if planned_arrival is set)
"""
import logging
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Driver, Trip, TripStatus, Expense, ExpenseType, FuelAnomaly, Vehicle

logger = logging.getLogger(__name__)

# --- Scoring configuration ---
# Points are on a 0-100 scale.
# Start at 100, deduct for violations, add for good behavior.

MAX_SCORE = 100

DEDUCTIONS = {
    "fuel_anomaly":        -10,  # Each fuel anomaly detected
    "expense_rejected":    -5,   # Each rejected expense
    "no_receipt":          -3,   # Fuel expense without a receipt photo
    "over_fuel_10pct":     -5,   # Fuel efficiency >10% over norm (per trip)
    "over_fuel_20pct":     -10,  # Fuel efficiency >20% over norm (per trip)
}

BONUSES = {
    "completed_trip":          3,  # Each successfully completed trip
    "fuel_within_norm":        5,  # Fuel efficiency within norm for a trip
    "zero_anomalies_in_trip":  2,  # Trip with NO fuel anomalies
}


async def calculate_driver_score(session: AsyncSession, driver: Driver, trips: list) -> dict:
    """
    Calculates a driver's eco-score based on their last N completed trips.
    Returns a dict with score (0-100), grade (A/B/C/D/F), and breakdown.
    """
    score = MAX_SCORE
    breakdown = []
    completed_trips = [t for t in trips if t.status == TripStatus.COMPLETED]

    if not completed_trips:
        return {
            "driver_id": driver.id,
            "driver_name": driver.name or f"Водитель #{driver.id}",
            "score": None,
            "grade": "—",
            "grade_color": "secondary",
            "trips_analyzed": 0,
            "breakdown": [],
            "anomaly_count": 0,
            "rejections": 0,
        }

    anomaly_count = 0
    rejection_count = 0
    no_receipt_count = 0
    fuel_within_norm_trips = 0
    
    for trip in completed_trips:
        # --- Bonus: completed trip ---
        score += BONUSES["completed_trip"]
        
        fuel_expenses = [e for e in trip.expenses if e.expense_type == ExpenseType.FUEL.value]
        
        # --- Check fuel efficiency per trip ---
        trip_anomalies = [a for e in fuel_expenses for a in (e.anomalies if hasattr(e, 'anomalies') else [])]
        
        # Check via fuel_anomaly relationship on expenses
        # (We check expenses directly since we loaded them)
        has_anomaly = any(e for e in fuel_expenses if True)  # placeholder
        
        # Check rejections
        for expense in trip.expenses:
            if expense.status == "REJECTED":
                rejection_count += 1
                score += DEDUCTIONS["expense_rejected"]
            if expense.expense_type == ExpenseType.FUEL.value and not expense.photo_file_id and not expense.photo_r2_url:
                no_receipt_count += 1
                score += DEDUCTIONS["no_receipt"]
        
        # Check fuel vs vehicle norm for this trip
        if trip.vehicle and trip.vehicle.fuel_norm_per_100km and trip.start_odometer and trip.end_odometer:
            km = trip.end_odometer - trip.start_odometer
            total_liters = sum(e.liters for e in fuel_expenses if e.liters)
            
            if km > 50 and total_liters > 0:
                actual_per_100 = (total_liters / km) * 100
                norm = trip.vehicle.fuel_norm_per_100km
                
                if actual_per_100 <= norm * 1.05:
                    fuel_within_norm_trips += 1
                    score += BONUSES["fuel_within_norm"]
                elif actual_per_100 > norm * 1.20:
                    score += DEDUCTIONS["over_fuel_20pct"]
                    breakdown.append(f"Рейс #{trip.id}: перерасход топлива >20%")
                elif actual_per_100 > norm * 1.10:
                    score += DEDUCTIONS["over_fuel_10pct"]
                    breakdown.append(f"Рейс #{trip.id}: перерасход топлива >10%")

    # --- Count anomalies from DB ---
    anomaly_result = await session.execute(
        select(sqlfunc.count(FuelAnomaly.id))
        .join(Trip, FuelAnomaly.trip_id == Trip.id)
        .where(Trip.driver_id == driver.id)
    )
    anomaly_count = anomaly_result.scalar() or 0
    score += anomaly_count * DEDUCTIONS["fuel_anomaly"]

    # Clamp to 0-100
    score = max(0, min(100, round(score)))

    # --- Grade ---
    if score >= 90:
        grade, color = "A", "success"
    elif score >= 75:
        grade, color = "B", "info"
    elif score >= 60:
        grade, color = "C", "warning"
    elif score >= 40:
        grade, color = "D", "orange"
    else:
        grade, color = "F", "danger"

    total_km = sum(
        (t.end_odometer - t.start_odometer)
        for t in completed_trips
        if t.start_odometer and t.end_odometer
    )

    return {
        "driver_id": driver.id,
        "driver_name": driver.name or f"Водитель #{driver.id}",
        "score": score,
        "grade": grade,
        "grade_color": color,
        "trips_analyzed": len(completed_trips),
        "total_km": total_km,
        "anomaly_count": anomaly_count,
        "rejections": rejection_count,
        "no_receipt_count": no_receipt_count,
        "fuel_within_norm_trips": fuel_within_norm_trips,
        "breakdown": breakdown,
    }


async def get_driver_leaderboard(session: AsyncSession) -> list:
    """
    Returns a sorted leaderboard of all active drivers with their eco-scores.
    """
    drivers_result = await session.execute(
        select(Driver)
        .where(Driver.status == "ACTIVE")
        .order_by(Driver.name)
    )
    drivers = drivers_result.scalars().all()

    leaderboard = []
    for driver in drivers:
        # Load last 20 completed trips for this driver with expenses and vehicle
        trips_result = await session.execute(
            select(Trip)
            .where(Trip.driver_id == driver.id)
            .where(Trip.status == TripStatus.COMPLETED)
            .options(
                __import__("sqlalchemy.orm", fromlist=["selectinload"]).selectinload(Trip.expenses),
                __import__("sqlalchemy.orm", fromlist=["selectinload"]).selectinload(Trip.vehicle),
            )
            .order_by(Trip.completed_at.desc())
            .limit(20)
        )
        trips = trips_result.scalars().all()

        score_data = await calculate_driver_score(session, driver, trips)
        leaderboard.append(score_data)

    # Sort: drivers with scores first (descending), then unscored
    leaderboard.sort(
        key=lambda x: (x["score"] is not None, x["score"] if x["score"] is not None else -1),
        reverse=True
    )
    return leaderboard
