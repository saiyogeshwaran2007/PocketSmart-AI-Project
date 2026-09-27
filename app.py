import os
import json
import uuid
import shutil
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union

from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form, Request, status, Cookie
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
import bcrypt
from jose import JWTError, jwt
from dotenv import load_dotenv

from models import (
    UserRegister, UserInDB, Token, TokenData,
    HomeBudgetInput, PartyBudgetInput, JewelryBudgetInput,
    RecommendationHistoryItem, UserSession
)
from gemini_utils import (
    get_home_recommendations,
    get_party_recommendations,
    get_jewelry_recommendations,
    usd_to_inr
)

# Load environment variables
load_dotenv()

# JWT and Security Settings
SECRET_KEY = os.getenv("SECRET_KEY", "pocketsmart_super_secret_jwt_key_2025")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# App Initialization
app = FastAPI(
    title="PocketSmart: AI Budget Planner",
    description="GenAI-powered cross-platform budget and recommendation assistant",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Static files and templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# In-memory Storage (Simulating Production DB & Session Store)
users_db: Dict[str, UserInDB] = {}
user_recommendations: Dict[str, List[RecommendationHistoryItem]] = {}
active_sessions: Dict[str, UserSession] = {}
blacklisted_tokens = set()

# Security helpers
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

# Initialize demo user
demo_password_hash = get_password_hash("password123")
users_db["sai"] = UserInDB(
    username="sai",
    email="sai@pocketsmart.ai",
    hashed_password=demo_password_hash,
    full_name="Sai Kumar"
)


# =====================================================================
# SECURITY & AUTHENTICATION HELPERS
# =====================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_token_from_request(request: Request, bearer_token: Optional[str] = Depends(oauth2_scheme)) -> Optional[str]:
    """Retrieve token either from Authorization Bearer header or HTTP-only Cookie."""
    if bearer_token:
        return bearer_token
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        if cookie_token.startswith("Bearer "):
            return cookie_token.split(" ")[1]
        return cookie_token
    return None

async def get_current_user_optional(request: Request, token: Optional[str] = Depends(get_token_from_request)) -> Optional[UserInDB]:
    if not token or token in blacklisted_tokens:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = users_db.get(username)
        return user
    except (JWTError, Exception):
        return None

async def get_current_active_user(request: Request, current_user: Optional[UserInDB] = Depends(get_current_user_optional)) -> UserInDB:
    if not current_user:
        # If web request, redirect to login; if API request, throw 401
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/login"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def save_upload_file(upload_file: UploadFile) -> str:
    """Save an uploaded image file securely to static/uploads."""
    ext = os.path.splitext(upload_file.filename)[1]
    if not ext:
        ext = ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return file_path


def save_to_history(username: str, recommendation_type: str, input_data: dict, result: dict):
    """Save recommendation query and result to user history."""
    if username not in user_recommendations:
        user_recommendations[username] = []
    
    # Generate concise summaries for quick dashboard/history rendering
    if recommendation_type == "home":
        rooms_list = input_data.get("rooms", [])
        rooms_str = ", ".join(rooms_list) if rooms_list else "Living Room"
        input_summary = f"Rooms: {rooms_str} | Lights: {input_data.get('num_lights', 0)} | Fans: {input_data.get('num_fans', 0)} | Furniture: {input_data.get('num_furniture', 0)}"
        alloc = len(result.get("budget_breakdown", []))
        result_summary = f"Total: ₹{input_data.get('total_budget', 0):,.2f} | {alloc} Categories Planned | Remaining: ₹{result.get('remaining_budget', 0):,.2f}"
    elif recommendation_type == "party":
        input_summary = f"Type: {input_data.get('party_type', 'Event')} | Guests: {input_data.get('num_guests', 0)} | Venue: {input_data.get('venue_type', 'Home')}"
        needs = []
        if input_data.get("needs_catering"): needs.append("Catering")
        if input_data.get("needs_decoration"): needs.append("Decoration")
        if input_data.get("needs_entertainment"): needs.append("Entertainment")
        input_summary += f" | Needs: {', '.join(needs) if needs else 'General'}"
        result_summary = f"Total: ₹{input_data.get('total_budget', 0):,.2f} | Venue & Catering Sourced | Remaining: ₹{result.get('remaining_budget', 0):,.2f}"
    else:  # jewelry
        has_img = "Yes" if input_data.get("image") or input_data.get("has_image") else "No"
        input_summary = f"Occasion: {input_data.get('occasion', 'Special')} | With outfit image: {has_img}"
        items_cnt = len(result.get("jewelry_recommendations", []))
        result_summary = f"Total: ₹{input_data.get('total_budget', 0):,.2f} | {items_cnt} Matched Pieces | Remaining: ₹{result.get('remaining_budget', 0):,.2f}"

    item = RecommendationHistoryItem(
        id=str(uuid.uuid4())[:8],
        timestamp=datetime.utcnow().strftime("%b %d, %Y, %I:%M %p"),
        recommendation_type=recommendation_type,
        input_data=input_data,
        input_summary=input_summary,
        result_summary=result_summary,
        full_result=result
    )
    user_recommendations[username].insert(0, item)
    return item


# Populate sample history for demo user 'sai'
sample_home_res = get_home_recommendations(HomeBudgetInput(total_budget=5000, num_lights=5, num_fans=4, num_furniture=2, num_dining_tables=1, rooms=["Living Room", "Kitchen"]))
save_to_history("sai", "home", {"total_budget": 5000, "num_lights": 5, "num_fans": 4, "num_furniture": 2, "num_dining_tables": 1, "rooms": ["Living Room", "Kitchen"]}, sample_home_res)

sample_party_res = get_party_recommendations(PartyBudgetInput(total_budget=5000, num_guests=3, party_type="Wedding", venue_type="Home", needs_catering=True, needs_decoration=True, needs_entertainment=True))
save_to_history("sai", "party", {"total_budget": 5000, "num_guests": 3, "party_type": "Wedding", "venue_type": "Home", "needs_catering": True, "needs_decoration": True, "needs_entertainment": True}, sample_party_res)

sample_jewelry_res = get_jewelry_recommendations(JewelryBudgetInput(total_budget=5000, occasion="Birthday", preferences="Minimalist gold"))
save_to_history("sai", "jewelry", {"total_budget": 5000, "occasion": "Birthday", "has_image": True}, sample_jewelry_res)


# =====================================================================
# TEMPLATE PAGES (FRONTEND ROUTES)
# =====================================================================

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, current_user: Optional[UserInDB] = Depends(get_current_user_optional)):
    """Main landing page introducing PocketSmart AI features."""
    return templates.TemplateResponse(request=request, name="index.html", context={"user": current_user})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, current_user: Optional[UserInDB] = Depends(get_current_user_optional)):
    """Serve the login page."""
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="login.html", context={"user": None})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, current_user: Optional[UserInDB] = Depends(get_current_user_optional)):
    """Serve the registration page."""
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="register.html", context={"user": None})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    """User dashboard displaying recent recommendations and quick planners."""
    history = user_recommendations.get(current_user.username, [])[:5]
    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "user": current_user,
        "recent_history": history
    })

@app.get("/home-planner", response_class=HTMLResponse)
async def home_planner_page(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    """Home budget planner page."""
    return templates.TemplateResponse(request=request, name="home_planner.html", context={"user": current_user})

@app.get("/party-planner", response_class=HTMLResponse)
async def party_planner_page(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    """Party budget planner page."""
    return templates.TemplateResponse(request=request, name="party_planner.html", context={"user": current_user})

@app.get("/jewelry-planner", response_class=HTMLResponse)
async def jewelry_planner_page(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    """Jewelry budget planner page."""
    return templates.TemplateResponse(request=request, name="jewelry_planner.html", context={"user": current_user})

@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    """User recommendation history review page."""
    history = user_recommendations.get(current_user.username, [])
    return templates.TemplateResponse(request=request, name="history.html", context={
        "user": current_user,
        "history": history
    })


# =====================================================================
# AUTHENTICATION & SESSION ENDPOINTS
# =====================================================================

@app.post("/register")
async def register_user(user_data: UserRegister):
    """Handle new user registration."""
    if user_data.username in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered. Please choose another or sign in."
        )
    
    hashed_pw = get_password_hash(user_data.password)
    new_user = UserInDB(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_pw,
        full_name=user_data.full_name or user_data.username
    )
    users_db[user_data.username] = new_user
    user_recommendations[user_data.username] = []

    # Auto generate access token
    access_token = create_access_token(data={"sub": new_user.username})
    response = JSONResponse(
        content={
            "message": "Registration successful",
            "access_token": access_token,
            "token_type": "bearer",
            "username": new_user.username
        },
        status_code=status.HTTP_201_CREATED
    )
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return response

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 compatible token login."""
    user = users_db.get(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # Track active session
    active_sessions[user.username] = UserSession(
        username=user.username,
        login_time=datetime.utcnow(),
        last_activity=datetime.utcnow(),
        token=access_token,
        user_data={"login_method": "password"}
    )

    response = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return response

@app.post("/logout")
async def logout(request: Request):
    """Logout user, blacklist token, and delete cookie."""
    token = await get_token_from_request(request)
    if token:
        blacklisted_tokens.add(token)
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username and username in active_sessions:
                del active_sessions[username]
        except JWTError:
            pass

    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response

@app.get("/session-info")
async def get_session_info(current_user: UserInDB = Depends(get_current_active_user)):
    """Retrieve metadata about the current user session."""
    if current_user.username in active_sessions:
        session = active_sessions[current_user.username]
        duration = int((datetime.utcnow() - session.login_time).total_seconds() // 60)
        return {
            "username": session.username,
            "email": current_user.email,
            "login_time": session.login_time.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "session_duration_minutes": duration,
            "user_data": session.user_data
        }
    return {
        "username": current_user.username,
        "email": current_user.email,
        "login_time": datetime.utcnow().isoformat(),
        "status": "active"
    }

@app.post("/session-data")
async def update_session_data(data: Dict[str, Any], current_user: UserInDB = Depends(get_current_active_user)):
    """Update user session custom metadata."""
    if current_user.username in active_sessions:
        active_sessions[current_user.username].user_data.update(data)
        active_sessions[current_user.username].last_activity = datetime.utcnow()
        return {"message": "Session data updated", "data": active_sessions[current_user.username].user_data}
    raise HTTPException(status_code=404, detail="No active session found")


# =====================================================================
# AI RECOMMENDATION CORE ENDPOINTS
# =====================================================================

# 1. HOME PLANNER ENDPOINTS
@app.post("/home-budget")
@app.post("/generate-home")
async def plan_home_budget(
    budget_input: HomeBudgetInput,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Generate home budget recommendations and persist to user history."""
    try:
        if current_user.username in active_sessions:
            active_sessions[current_user.username].user_data["last_home_budget"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "budget": budget_input.total_budget,
                "requirements": budget_input.dict()
            }
            active_sessions[current_user.username].last_activity = datetime.utcnow()

        # Call Gemini AI layer
        result = get_home_recommendations(budget_input)

        # Save to history
        save_to_history(
            username=current_user.username,
            recommendation_type="home",
            input_data=budget_input.dict(),
            result=result
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating home recommendations: {str(e)}")


# 2. PARTY PLANNER ENDPOINTS
@app.post("/party-budget")
@app.post("/generate-party")
async def plan_party_budget(
    budget_input: PartyBudgetInput,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Generate party budget recommendations and persist to user history."""
    try:
        if current_user.username in active_sessions:
            active_sessions[current_user.username].user_data["last_party_budget"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "budget": budget_input.total_budget,
                "party_type": budget_input.party_type,
                "guests": budget_input.num_guests
            }
            active_sessions[current_user.username].last_activity = datetime.utcnow()

        # Call Gemini AI layer
        result = get_party_recommendations(budget_input)

        # Save to history
        save_to_history(
            username=current_user.username,
            recommendation_type="party",
            input_data=budget_input.dict(),
            result=result
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating party recommendations: {str(e)}")


# 3. JEWELRY PLANNER ENDPOINTS (MULTIMODAL SUPPORT)
@app.post("/jewelry-budget")
@app.post("/generate-jewelry")
async def plan_jewelry_budget(
    total_budget: float = Form(...),
    occasion: str = Form(...),
    preferences: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Generate jewelry recommendations with optional outfit image analysis."""
    try:
        budget_input = JewelryBudgetInput(
            total_budget=total_budget,
            occasion=occasion,
            preferences=preferences
        )

        image_path = None
        image_url = None
        if image and image.filename:
            image_path = save_upload_file(image)
            image_url = f"/static/uploads/{os.path.basename(image_path)}"

        if current_user.username in active_sessions:
            active_sessions[current_user.username].user_data["last_jewelry_budget"] = {
                "timestamp": datetime.utcnow().isoformat(),
                "budget": total_budget,
                "occasion": occasion,
                "has_image": bool(image_path)
            }
            active_sessions[current_user.username].last_activity = datetime.utcnow()

        # Call Gemini AI Layer
        result = get_jewelry_recommendations(budget_input, image_path=image_path)
        if image_url:
            result["uploaded_image_url"] = image_url

        # Save to history
        input_data = budget_input.dict()
        if image_url:
            input_data["image"] = image_url
            input_data["has_image"] = True

        save_to_history(
            username=current_user.username,
            recommendation_type="jewelry",
            input_data=input_data,
            result=result
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating jewelry recommendations: {str(e)}")


# 4. RECOMMENDATION HISTORY & DETAILS API
@app.get("/recommendation-history")
async def get_user_recommendation_history(current_user: UserInDB = Depends(get_current_active_user)):
    """Retrieve full history of recommendations for the logged in user."""
    items = user_recommendations.get(current_user.username, [])
    history_data = []
    for item in items:
        history_data.append({
            "id": item.id,
            "timestamp": item.timestamp,
            "type": item.recommendation_type,
            "input": item.input_summary,
            "summary": item.result_summary,
            "full_result": item.full_result
        })
    return {"history": history_data}

@app.get("/recommendation-details/{recommendation_id}")
async def get_recommendation_details(
    recommendation_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Retrieve full details of a specific past recommendation."""
    items = user_recommendations.get(current_user.username, [])
    for item in items:
        if item.id == recommendation_id:
            return {
                "id": item.id,
                "timestamp": item.timestamp,
                "type": item.recommendation_type,
                "input": item.input_summary,
                "full_result": item.full_result
            }
    raise HTTPException(status_code=404, detail="Recommendation not found")


# =====================================================================
# STARTUP & BACKGROUND SESSION CLEANUP
# =====================================================================

@app.on_event("startup")
async def setup_session_cleanup():
    """Background task to clean up expired sessions."""
    async def cleanup_expired_sessions():
        while True:
            try:
                now = datetime.utcnow()
                expired = []
                for uname, sess in list(active_sessions.items()):
                    if (now - sess.last_activity).total_seconds() > (ACCESS_TOKEN_EXPIRE_MINUTES * 60):
                        expired.append(uname)
                for uname in expired:
                    if uname in active_sessions:
                        del active_sessions[uname]
            except Exception:
                pass
            await asyncio.sleep(300) # Check every 5 minutes

    asyncio.create_task(cleanup_expired_sessions())


if __name__ == "__main__":
    import uvicorn
    print("Starting PocketSmart: AI Budget Planner on http://localhost:8000 ...")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
