# models.py
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class Mode(BaseModel):
    mode: str

class Variables(BaseModel):
    arriveBy: Optional[bool]
    banned: Dict[str, Any]
    bikeReluctance: Optional[float] = None
    carReluctance: Optional[float] = None
    date: str
    fromPlace: str
    modes: List[Mode]
    numItineraries: int
    preferred: Optional[Dict[str, Any]] = None
    time: str
    toPlace: str
    unpreferred: Optional[Dict[str, Any]] = None
    walkReluctance: Optional[float] = None
    walkSpeed: Optional[float] = None
    wheelchair: bool

class RouteSearchRequest(BaseModel):
    batchId: str
    query: str
    variables: Variables
    
class Attraction(BaseModel):
    attraction_name: str
    attraction_category: str
    attraction_lon: float
    attraction_lat: float

class StopResponse(BaseModel):
    stop_code: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    stop_latlon: str
    attractions: List[Attraction]