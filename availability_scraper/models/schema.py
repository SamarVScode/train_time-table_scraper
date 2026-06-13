from dataclasses import dataclass, asdict
from typing import List, Optional

@dataclass
class AvailabilityStatus:
    date: str
    status: str
    prediction: Optional[str] = None
    fare: Optional[str] = None

@dataclass
class AvailabilityResponse:
    success: bool
    train_number: str
    from_station: str
    to_station: str
    quota: str
    travel_class: str
    availability: List[AvailabilityStatus]
    error: Optional[str] = None

    def to_dict(self):
        return asdict(self)
