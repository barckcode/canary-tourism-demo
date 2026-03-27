"""Pre-defined tourism events for Tenerife 2025-2026."""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import TourismEvent

logger = logging.getLogger(__name__)

EVENTS = [
    # 2025 events (historical)
    {
        "name": "Carnaval de Santa Cruz 2025",
        "description": "One of the world's largest carnivals",
        "category": "cultural",
        "start_date": "2025-01-17",
        "end_date": "2025-02-23",
        "impact_estimate": "+20% arrivals",
        "location": "Santa Cruz de Tenerife",
        "source": "system",
    },
    {
        "name": "Semana Santa 2025",
        "category": "cultural",
        "start_date": "2025-04-13",
        "end_date": "2025-04-20",
        "impact_estimate": "+12% arrivals",
        "location": "Island-wide",
        "source": "system",
    },
    # 2026 events
    {
        "name": "Carnaval de Santa Cruz 2026",
        "description": "1M+ asistentes, 84% ocupacion, ~40M EUR impacto economico",
        "category": "cultural",
        "start_date": "2026-01-16",
        "end_date": "2026-02-22",
        "impact_estimate": "+20% arrivals",
        "location": "Santa Cruz de Tenerife",
        "source": "system",
    },
    {
        "name": "Carnaval de Maspalomas",
        "category": "cultural",
        "start_date": "2026-03-10",
        "end_date": "2026-03-22",
        "impact_estimate": "+8% south arrivals",
        "location": "South",
        "source": "system",
    },
    {
        "name": "Semana Santa 2026",
        "category": "cultural",
        "start_date": "2026-03-29",
        "end_date": "2026-04-05",
        "impact_estimate": "+12% arrivals",
        "location": "Island-wide",
        "source": "system",
    },
    {
        "name": "XV Feria del Queso de Canarias",
        "category": "cultural",
        "start_date": "2026-04-11",
        "end_date": "2026-04-12",
        "impact_estimate": "+5% north arrivals",
        "location": "La Orotava",
        "source": "system",
    },
    {
        "name": "Whale watching peak season",
        "description": "Peak whale and dolphin watching season",
        "category": "cultural",
        "start_date": "2026-03-01",
        "end_date": "2026-05-31",
        "impact_estimate": "+10% eco-tourism",
        "location": "West coast",
        "source": "system",
    },
    {
        "name": "Air Serbia: Belgrade route",
        "description": "New direct route Belgrade-Tenerife",
        "category": "connectivity",
        "start_date": "2026-10-01",
        "impact_estimate": "+2% Eastern European arrivals",
        "location": "TFS Airport",
        "source": "system",
    },
    {
        "name": "Binter: daily Asturias flights",
        "description": "Daily flights Asturias-Tenerife",
        "category": "connectivity",
        "start_date": "2026-10-01",
        "impact_estimate": "+3% domestic arrivals",
        "location": "TFN Airport",
        "source": "system",
    },
    {
        "name": "Vueling summer capacity boost",
        "description": "+52,000 international seats",
        "category": "connectivity",
        "start_date": "2026-06-01",
        "end_date": "2026-09-30",
        "impact_estimate": "+8% international arrivals",
        "location": "TFS Airport",
        "source": "system",
    },
    {
        "name": "Peninsula tourism decline",
        "description": "-86,000 air seats Jan-Feb vs prior year",
        "category": "external",
        "start_date": "2026-01-01",
        "end_date": "2026-02-28",
        "impact_estimate": "+5% redirected to Canarias",
        "location": "Island-wide",
        "source": "system",
    },
    {
        "name": "Canarias tiene un limite protests",
        "description": "Anti-overtourism movement, Fodor's No-List 2026",
        "category": "regulation",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "impact_estimate": "-3% to -5% bookings",
        "location": "Island-wide",
        "source": "system",
    },
    {
        "name": "Dia de Canarias",
        "description": "Regional holiday celebrating Canarian identity and culture",
        "category": "cultural",
        "start_date": "2026-05-30",
        "end_date": "2026-05-30",
        "impact_estimate": "+5% domestic tourism",
        "location": "Island-wide",
        "source": "system",
    },
    {
        "name": "Corpus Christi La Orotava",
        "description": "Famous flower carpet festival in La Orotava",
        "category": "cultural",
        "start_date": "2026-06-18",
        "end_date": "2026-06-18",
        "impact_estimate": "+10% north arrivals",
        "location": "La Orotava",
        "source": "system",
    },
    {
        "name": "Noche de San Juan",
        "description": "Traditional midsummer celebration with bonfires on the beach",
        "category": "cultural",
        "start_date": "2026-06-23",
        "end_date": "2026-06-24",
        "impact_estimate": "+8% coastal tourism",
        "location": "Coastal towns",
        "source": "system",
    },
    {
        "name": "Festival Arona Summer",
        "description": "Major summer music festival in the south of Tenerife",
        "category": "cultural",
        "start_date": "2026-07-15",
        "end_date": "2026-08-15",
        "impact_estimate": "+15% south arrivals",
        "location": "Arona",
        "source": "system",
    },
]


def seed_events(db: Session) -> int:
    """Insert pre-defined events if the tourism_events table is empty.

    Returns the number of events inserted (0 if table was already populated).
    """
    count = db.execute(text("SELECT COUNT(*) FROM tourism_events")).scalar()
    if count and count > 0:
        logger.info("Tourism events already seeded (%d rows), skipping.", count)
        return 0

    for event_data in EVENTS:
        db.add(TourismEvent(**event_data))

    db.commit()
    logger.info("Seeded %d tourism events.", len(EVENTS))
    return len(EVENTS)
