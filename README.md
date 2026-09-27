# PocketSmart AI: Your Smart Budget & Recommendation Assistant

**PocketSmart AI** is a full-stack GenAI-powered cross-platform budget and recommendation system. It delivers personalized, budget-aware recommendations across home interiors, party event planning, and occasion-based jewelry selection with multimodal image analysis.

---

## 🌟 Key Features & Scenarios

### 1. 🏠 Home Interior Budget Planner
* **Input Parameters**: Total budget, room selection (Living Room, Kitchen, Bedroom, Balcony), and quantity specifications for fixtures (lighting, ceiling fans, furniture pieces, dining tables).
* **AI Analysis**: Allocates funds across categories (Lighting, Fans, Furniture, Dining Sets), suggests cost-effective Indian brands, calculates budget utilization, and provides shopping links for **Amazon India, Flipkart, IKEA, Myntra, and Ajio**.
* **Budget Summary**: Real-time breakdown table with item counts, estimated costs, % allocation, remaining buffer, and space-optimization tips.

### 2. 🎉 AI-Based Party Budget Planner
* **Input Parameters**: Total event budget, number of guests, party type (Birthday, Wedding, Anniversary, Corporate, House Party), venue type (Home, Banquet Hall, Resort, Outdoor Lawn, Rooftop, Farmhouse), and requirement checkboxes (Catering, Decoration, Entertainment).
* **AI Analysis**: Proportional allocation across Venue booking, Catering/Buffet platters, Theme decor props, Sound/DJ & games, and contingency buffer.
* **Direct Vendor & Platform Links**: Sourced from **Swiggy, Zomato, BigBasket, BookMyShow, MakeMyTrip, Booking.com, OYO Rooms, NoBroker, Amazon, and Flipkart**.

### 3. 💎 Multimodal Jewelry Budget Planner
* **Input Parameters**: Total budget, occasion (Wedding, Birthday, Festival, Cocktail Party), style preferences, and **optional outfit image upload**.
* **Multimodal AI Analysis**: Analyzes outfit color palette, neckline, style, and formality level from the image.
* **AI Recommendations**: Matches necklaces/chokers, earrings/jhumkas, bracelets/kadas, and statement rings within budget.
* **Direct Platform Links**: Sourced from **Tanishq, CaratLane, BlueStone, Melorra, Amazon, Flipkart, and Meesho**.

### 4. 📊 User Dashboard & History Tracker
* **Session & Auth**: Secure registration and login using JWT tokens and HTTP-only cookies.
* **Interactive History**: View all past budget plans with real-time modal details, breakdown summaries, and PDF print/export capabilities.
* **Session Management**: Automatic background cleanup of inactive user sessions.

---

## 🏗️ Architecture & Tech Stack

```
PocketSmart-AI/
├── static/
│   ├── uploads/              # Uploaded outfit images
│   └── styles.css            # Custom responsive CSS design system
├── templates/
│   ├── index.html            # Landing page (Hero, features, testimonials)
│   ├── login.html            # User authentication
│   ├── register.html         # User registration
│   ├── dashboard.html        # Main user portal & activity feed
│   ├── home_planner.html     # Home interior planning interface
│   ├── party_planner.html    # Party event budget interface
│   ├── jewelry_planner.html  # Multimodal jewelry planner interface
│   └── history.html          # Past recommendation logs & detail view
├── app.py                    # Main FastAPI backend application
├── main.py                   # Server startup script
├── models.py                 # Pydantic data models & schemas
├── gemini_utils.py           # Google Gemini AI integration & prompt logic
├── test_app.py               # Automated test suite
├── requirements.txt          # Python dependencies
├── .env                      # Environment configuration
└── README.md                 # Project documentation
```

### Core Technologies
* **Backend**: FastAPI, Uvicorn, Starlette, Jinja2Templates, Pydantic
* **AI Engine**: Google Gemini API (`google-generativeai` / `gemini-1.5-flash` / `gemini-2.0-flash`)
* **Security**: JWT Authentication (`python-jose`), `bcrypt` password hashing
* **Frontend**: Responsive HTML5, CSS3 Glassmorphism UI, Vanilla JavaScript (Fetch API)

---

## 🚀 Quick Start Guide

### 1. Prerequisites
* Python 3.10+ (tested with Python 3.14)
* Google Gemini API Key ([Get a free key from Google AI Studio](https://aistudio.google.com/))

### 2. Installation
```bash
# Clone or navigate to the directory
cd PocketSmart-AI

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create or edit `.env` in the root folder:
```ini
GEMINI_API_KEY=your_google_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
SECRET_KEY=pocketsmart_super_secure_jwt_secret_key_2025
ACCESS_TOKEN_EXPIRE_MINUTES=60
```
*(Note: If no API key is set, PocketSmart runs in resilient fallback mode with smart heuristic estimation engines).*

### 4. Run Application
```bash
python main.py
```
Open your browser and navigate to: **[http://localhost:8000](http://localhost:8000)**

### 5. Seed Demo Credentials
* **Username**: `sai`
* **Password**: `password123`
*(Or register a new account on `/register`)*

---

## 🧪 Running Automated Tests
Run the comprehensive test suite:
```bash
python test_app.py
```
All endpoints, authentication flows, session handling, and recommendation pipelines will execute and validate response integrity.
