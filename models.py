from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserInDB(BaseModel):
    username: str
    email: str
    hashed_password: str
    full_name: Optional[str] = None
    created_at: datetime = datetime.utcnow()

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class HomeBudgetInput(BaseModel):
    total_budget: float
    num_lights: int = 4
    num_fans: int = 2
    num_furniture: int = 2
    num_dining_tables: int = 1
    rooms: Optional[List[str]] = []
    has_living_room: bool = True
    has_kitchen: bool = False
    has_bedroom: bool = False
    additional_requirements: Optional[str] = None

class PartyBudgetInput(BaseModel):
    total_budget: float
    num_guests: int = 10
    party_type: str = "Birthday"
    venue_type: str = "Home"
    needs_catering: bool = True
    needs_decoration: bool = True
    needs_entertainment: bool = True
    additional_requirements: Optional[str] = None

class JewelryBudgetInput(BaseModel):
    total_budget: float
    occasion: str = "Wedding"
    preferences: Optional[str] = None

class RecommendationHistoryItem(BaseModel):
    id: str
    timestamp: str
    recommendation_type: str # "home", "party", "jewelry"
    input_data: Dict[str, Any]
    input_summary: str
    result_summary: str
    full_result: Dict[str, Any]

class UserSession(BaseModel):
    username: str
    login_time: datetime
    last_activity: datetime
    token: str
    user_data: Dict[str, Any] = {}
