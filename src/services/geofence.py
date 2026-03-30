import math
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Geofence, Trip, TripEvent

logger = logging.getLogger(__name__)

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance in meters between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371000 # Radius of earth in meters.
    return c * r

async def check_geofence_arrival(session: AsyncSession, trip: Trip, current_lat: float, current_lng: float):
    """
    Checks if a truck has entered any active geofence.
    If yes, triggers a TripEvent if it doesn't already exist for this trip.
    """
    if not trip:
        return

    # 1. Fetch active geofences
    stmt = select(Geofence).where(Geofence.is_active == True)
    result = await session.execute(stmt)
    geofences = result.scalars().all()

    for fence in geofences:
        distance = haversine(current_lat, current_lng, fence.latitude, fence.longitude)
        
        if distance <= fence.radius_meters:
            # We are inside the fence!
            
            # 2. Check if this event was already triggered for this trip
            # To avoid spamming events on every location update
            event_stmt = select(TripEvent).where(
                TripEvent.trip_id == trip.id,
                TripEvent.event_type == fence.event_type,
                TripEvent.location_name == fence.name
            )
            event_exists = (await session.execute(event_stmt)).scalars().first()
            
            if not event_exists:
                # 3. Create automatic event
                new_event = TripEvent(
                    trip_id=trip.id,
                    event_type=fence.event_type,
                    location_name=fence.name
                )
                session.add(new_event)
                logger.info(f"Geofence event triggered: Trip {trip.id} arrived at {fence.name} ({fence.event_type})")
                
                # Optionally send a notification here too
                # For now just commit the event
                return new_event
    return None
