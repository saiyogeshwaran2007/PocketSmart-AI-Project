import os
import json
import re
import urllib.parse
from typing import Optional, Dict, Any, List
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# Configure API Key
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

gemini_model = None

def init_gemini():
    global gemini_model
    if not API_KEY:
        print("[WARN] GEMINI_API_KEY / GOOGLE_API_KEY not found in environment variables. Running in resilient mode with built-in heuristic AI recommendation engine.")
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=API_KEY)
        # Prefer gemini-1.5-flash or gemini-2.0-flash
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        gemini_model = genai.GenerativeModel(model_name)
        print(f"[INFO] Gemini model initialized successfully: {model_name}")
        return gemini_model
    except Exception as e:
        print(f"[ERROR] Failed to initialize Google Generative AI: {e}")
        return None

# Initialize on module load
init_gemini()


def extract_json_from_response(text: str) -> dict:
    """Extract and parse JSON safely from Gemini model response."""
    if not text:
        return {}
    
    # Clean code blocks if present
    cleaned = text.strip()
    if "```json" in cleaned:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
    elif "```" in cleaned:
        match = re.search(r"```\s*([\s\S]*?)\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()

    try:
        return json.loads(cleaned)
    except Exception as e:
        # Fallback regex search for outer JSON object
        try:
            start_idx = cleaned.find("{")
            end_idx = cleaned.rfind("}")
            if start_idx != -1 and end_idx != -1:
                return json.loads(cleaned[start_idx : end_idx + 1])
        except Exception:
            pass
        print(f"[ERROR] Failed to parse JSON from AI response: {e}")
        print("Raw response:\n", text)
        return {}


def usd_to_inr(amount_usd: float, exchange_rate: float = 83.0) -> float:
    """Convert USD amount to INR using the specified exchange rate."""
    return round(amount_usd * exchange_rate, 2)


# =====================================================================
# 1. HOME INTERIOR RECOMMENDATIONS
# =====================================================================

def get_home_recommendations(budget_input) -> dict:
    """Generate home interior recommendations within budget in INR for Indian market."""
    total_budget = float(budget_input.total_budget)
    num_lights = getattr(budget_input, 'num_lights', 0)
    num_fans = getattr(budget_input, 'num_fans', 0)
    num_furniture = getattr(budget_input, 'num_furniture', 0)
    num_dining_tables = getattr(budget_input, 'num_dining_tables', 0)
    rooms = getattr(budget_input, 'rooms', [])
    if isinstance(rooms, str):
        rooms = [r.strip() for r in rooms.split(',') if r.strip()]
    
    has_living_room = "Living Room" in rooms or getattr(budget_input, 'has_living_room', False)
    has_kitchen = "Kitchen" in rooms or getattr(budget_input, 'has_kitchen', False)
    has_bedroom = "Bedroom" in rooms or getattr(budget_input, 'has_bedroom', False)
    additional_req = getattr(budget_input, 'additional_requirements', None) or "None"

    prompt = f"""
I need interior design product recommendations for a home in India with a total budget of ₹{total_budget:.2f}.
Requirements:
- {num_lights} lights/lighting fixtures
- {num_fans} ceiling fans
- {num_furniture} furniture pieces
- {num_dining_tables} dining tables

Additional rooms to consider:
{("- Living room" if has_living_room else "")}
{("- Kitchen" if has_kitchen else "")}
{("- Bedroom" if has_bedroom else "")}

Additional requirements: {additional_req}

Please provide a detailed budget breakdown with product recommendations **available in India**.
Use **Indian brands and pricing**. Include **search terms** suitable for Indian shopping platforms.

Format your response as JSON with the following structure:
{{
  "total_budget": {total_budget:.2f},
  "budget_breakdown": [
    {{
      "category": "Lighting",
      "allocation": 0.0,
      "items": [
        {{
          "name": "LED Warm White Ceiling Light",
          "description": "Energy-efficient LED bulbs for ambient lighting",
          "estimated_price": 0.0,
          "quantity": {max(num_lights, 1)},
          "search_terms": "LED Warm White Ceiling Light"
        }}
      ]
    }},
    {{
      "category": "Ceiling_fans",
      "allocation": 0.0,
      "items": [
        {{
          "name": "Havells Decorative High-Speed Ceiling Fan",
          "description": "Energy saving 1200mm high speed ceiling fan",
          "estimated_price": 0.0,
          "quantity": {max(num_fans, 1)},
          "search_terms": "Havells 1200mm Ceiling Fan"
        }}
      ]
    }},
    {{
      "category": "Furniture",
      "allocation": 0.0,
      "items": [
        {{
          "name": "Ergonomic Accent Chairs / Sofa",
          "description": "Modern comfortable seating",
          "estimated_price": 0.0,
          "quantity": {max(num_furniture, 1)},
          "search_terms": "Living room wooden furniture"
        }}
      ]
    }}
  ],
  "calculation_table": [
    {{
      "category": "Lighting",
      "items_count": {num_lights},
      "total_cost": 0.0,
      "percentage_of_budget": 0.0
    }}
  ],
  "remaining_budget": 0.0,
  "additional_suggestions": [
    "Consider purchasing multi-functional furniture for space optimization",
    "Look for seasonal sales and festive discounts on online marketplaces",
    "Prioritize essential fixtures first and postpone optional decorative accents"
  ]
}}

Ensure all costs are in INR and the sum of item costs * quantities stays strictly within the total budget of ₹{total_budget:.2f}.
Include search terms for each item to find on shopping websites like Flipkart, Amazon India, IKEA, Myntra, Ajio.
"""
    result = None
    if gemini_model:
        try:
            response = gemini_model.generate_content(prompt)
            result = extract_json_from_response(response.text)
        except Exception as e:
            print(f"[WARN] Gemini call failed for home recommendations: {e}. Falling back to smart generator.")
            result = None

    if not result or "budget_breakdown" not in result:
        result = _fallback_home_recommendations(total_budget, num_lights, num_fans, num_furniture, num_dining_tables, rooms)

    # Ensure total_budget and remaining_budget are consistent
    result["total_budget"] = float(result.get("total_budget", total_budget))
    
    # Calculate calculation table and add shopping links
    calc_table = []
    total_spent = 0.0

    for category in result.get("budget_breakdown", []):
        cat_name = category.get("category", "General")
        cat_total = 0.0
        cat_items_count = 0
        
        for item in category.get("items", []):
            qty = int(item.get("quantity", 1))
            price = float(item.get("estimated_price", 0.0))
            item_total = price * qty
            cat_total += item_total
            cat_items_count += qty
            total_spent += item_total

            search_terms = item.get("search_terms") or item.get("name", "")
            encoded_query = urllib.parse.quote_plus(search_terms)
            
            item["shopping_links"] = {
                "amazon": f"https://www.amazon.in/s?k={encoded_query}",
                "flipkart": f"https://www.flipkart.com/search?q={encoded_query}",
                "ikea": f"https://www.ikea.com/in/en/search/?q={encoded_query}",
                "myntra": f"https://www.myntra.com/{encoded_query}",
                "ajio": f"https://www.ajio.com/search/?text={encoded_query}"
            }
        
        category["allocation"] = round(cat_total, 2)
        pct = round((cat_total / total_budget * 100) if total_budget > 0 else 0, 1)
        calc_table.append({
            "category": cat_name,
            "items_count": cat_items_count,
            "total_cost": round(cat_total, 2),
            "percentage_of_budget": pct
        })

    result["calculation_table"] = calc_table
    result["remaining_budget"] = max(0.0, round(total_budget - total_spent, 2))
    
    return result


def _fallback_home_recommendations(budget: float, lights: int, fans: int, furniture: int, dining: int, rooms: List[str]) -> dict:
    """Smart fallback generator for home budget planning."""
    lights = max(lights, 1)
    fans = max(fans, 1)
    furniture = max(furniture, 1)
    dining = max(dining, 1 if "Kitchen" in rooms else 0)

    # Proportional weights
    w_lights = 0.20
    w_fans = 0.25
    w_furniture = 0.35
    w_dining = 0.15 if dining > 0 else 0.0
    w_decor = 0.05

    total_w = w_lights + w_fans + w_furniture + w_dining + w_decor
    w_lights /= total_w
    w_fans /= total_w
    w_furniture /= total_w
    w_dining /= total_w

    alloc_lights = budget * w_lights
    alloc_fans = budget * w_fans
    alloc_furn = budget * w_furniture
    alloc_dining = budget * w_dining

    light_price = round(alloc_lights / lights, 2)
    fan_price = round(alloc_fans / fans, 2)
    furn_price = round(alloc_furn / furniture, 2)
    dining_price = round(alloc_dining / max(dining, 1), 2) if dining > 0 else 0.0

    breakdown = [
        {
            "category": "Lighting",
            "allocation": round(alloc_lights, 2),
            "items": [
                {
                    "name": "Philips / Syska LED Ceiling Lights & Panel Fixtures",
                    "description": "Energy-efficient warm white ambient LED lighting with modern diffuser",
                    "estimated_price": light_price,
                    "quantity": lights,
                    "search_terms": "Philips Warm White LED ceiling lights"
                }
            ]
        },
        {
            "category": "Ceiling_fans",
            "allocation": round(alloc_fans, 2),
            "items": [
                {
                    "name": "Havells / Atomberg BLDC Energy Saver Ceiling Fan",
                    "description": "High air-delivery 1200mm decorative ceiling fan with remote control",
                    "estimated_price": fan_price,
                    "quantity": fans,
                    "search_terms": "Havells Atomberg 1200mm BLDC ceiling fan"
                }
            ]
        },
        {
            "category": "Furniture",
            "allocation": round(alloc_furn, 2),
            "items": [
                {
                    "name": "Modern Minimalist Wooden Accent Chair / Coffee Table Set",
                    "description": "Solid Sheesham wood crafted durable furniture with ergonomic cushions",
                    "estimated_price": furn_price,
                    "quantity": furniture,
                    "search_terms": "Modern wooden furniture living room"
                }
            ]
        }
    ]

    if dining > 0:
        breakdown.append({
            "category": "Dining_tables",
            "allocation": round(alloc_dining, 2),
            "items": [
                {
                    "name": "Compact Engineered Wood Dining Table Set",
                    "description": "Space-saving 4-seater dining table with comfortable cushioned chairs",
                    "estimated_price": dining_price,
                    "quantity": dining,
                    "search_terms": "4 seater dining table set engineered wood"
                }
            ]
        })

    return {
        "total_budget": budget,
        "budget_breakdown": breakdown,
        "remaining_budget": round(budget * 0.05, 2),
        "additional_suggestions": [
            "Consider purchasing modular and stackable furniture for space efficiency.",
            "Look for bundle deals on lighting and electrical fixtures on Amazon and Flipkart.",
            "Choose neutral color palettes for curtains and upholstery to maximize spatial warmth."
        ]
    }


# =====================================================================
# 2. PARTY BUDGET RECOMMENDATIONS
# =====================================================================

def get_party_recommendations(budget_input) -> dict:
    """Generate party planning recommendations within budget in INR for Indian market."""
    total_budget = float(budget_input.total_budget)
    num_guests = int(getattr(budget_input, 'num_guests', 10))
    party_type = getattr(budget_input, 'party_type', 'Birthday')
    venue_type = getattr(budget_input, 'venue_type', 'Home')
    needs_catering = getattr(budget_input, 'needs_catering', True)
    needs_decoration = getattr(budget_input, 'needs_decoration', True)
    needs_entertainment = getattr(budget_input, 'needs_entertainment', True)
    additional_req = getattr(budget_input, 'additional_requirements', None) or "None"

    prompt = f"""
I need party planning recommendations for India with a total budget of ₹{total_budget:.2f}.

Party details:
- Type: {party_type}
- Number of guests: {num_guests}
- Venue type: {venue_type}
- Catering needed: {("Yes" if needs_catering else "No")}
- Decoration needed: {("Yes" if needs_decoration else "No")}
- Entertainment needed: {("Yes" if needs_entertainment else "No")}
- Additional requirements: {additional_req}

Please provide a detailed budget breakdown with specific recommendations available in India using INR prices.
Use Indian brands, services, and typical cost expectations.

Format your response as JSON with the following structure:
{{
  "total_budget": {total_budget:.2f},
  "budget_breakdown": [
    {{
      "category": "venue",
      "allocation": 0.0,
      "items": [
        {{
          "name": "{venue_type} Space Booking / Setup",
          "description": "Venue reservation or home ambient setup for {num_guests} guests",
          "estimated_price": 0.0,
          "quantity": 1,
          "search_terms": "{venue_type} party venue booking"
        }}
      ]
    }},
    {{
      "category": "food",
      "allocation": 0.0,
      "items": [
        {{
          "name": "Buffet Catering / Party Platter for {num_guests} guests",
          "description": "Starter, main course, and dessert package",
          "estimated_price": 0.0,
          "quantity": 1,
          "search_terms": "Party catering bulk food order"
        }}
      ]
    }},
    {{
      "category": "decoration",
      "allocation": 0.0,
      "items": [
        {{
          "name": "Theme Balloon Arch & Backdrop Banner",
          "description": "Customized {party_type} theme decor kit with fairy lights",
          "estimated_price": 0.0,
          "quantity": 1,
          "search_terms": "{party_type} decoration party props kit"
        }}
      ]
    }},
    {{
      "category": "entertainment",
      "allocation": 0.0,
      "items": [
        {{
          "name": "Sound System / DJ Playlist / Party Games",
          "description": "Bluetooth party speaker setup and interactive board games",
          "estimated_price": 0.0,
          "quantity": 1,
          "search_terms": "Party bluetooth speaker interactive games"
        }}
      ]
    }},
    {{
      "category": "contingency",
      "allocation": 0.0,
      "items": [
        {{
          "name": "Miscellaneous & Emergency Buffer",
          "description": "Reserve for extra drinks, disposable cutlery, and surprise guests",
          "estimated_price": 0.0,
          "quantity": 1,
          "search_terms": "Party disposable tableware cutlery set"
        }}
      ]
    }}
  ],
  "venue_suggestions": [
    {{
      "name": "{venue_type} Celebration Spot",
      "type": "{venue_type}",
      "capacity": {num_guests},
      "estimated_cost": 0.0,
      "search_terms": "{venue_type} party hall near me"
    }}
  ],
  "remaining_budget": 0.0,
  "additional_suggestions": [
    "Opt for buffet-style catering to keep per-plate costs optimized for {num_guests} people.",
    "Utilize DIY backdrop kits with fairy lights to save substantially on decorator fees.",
    "Curate a collaborative Spotify playlist instead of hiring a full sound technician for intimate gatherings."
  ]
}}

Ensure all costs are in INR and total does not exceed the given budget.
Provide search terms suitable for Indian websites such as BookMyShow, Swiggy, Zomato, BigBasket, Flipkart, Amazon, MakeMyTrip, OYO, NoBroker.
"""
    result = None
    if gemini_model:
        try:
            response = gemini_model.generate_content(prompt)
            result = extract_json_from_response(response.text)
        except Exception as e:
            print(f"[WARN] Gemini call failed for party recommendations: {e}. Falling back to smart generator.")
            result = None

    if not result or "budget_breakdown" not in result:
        result = _fallback_party_recommendations(total_budget, num_guests, party_type, venue_type, needs_catering, needs_decoration, needs_entertainment)

    result["total_budget"] = float(result.get("total_budget", total_budget))

    # Define platform mappings per category
    category_platforms = {
        "venue": ["google", "booking", "makemytrip", "oyorooms", "nobroker"],
        "catering": ["swiggy", "zomato", "bigbasket", "amazon", "flipkart"],
        "food": ["swiggy", "zomato", "bigbasket", "amazon", "flipkart"],
        "drinks": ["swiggy", "zomato", "bigbasket", "amazon", "flipkart"],
        "decoration": ["amazon", "flipkart", "meesho", "myntra"],
        "entertainment": ["bookmyshow", "amazon", "flipkart"],
        "gifts": ["amazon", "flipkart", "myntra", "meesho"],
        "photography": ["google", "amazon", "flipkart"],
        "music": ["amazon", "flipkart", "bookmyshow"],
        "games": ["amazon", "flipkart"],
        "accessories": ["amazon", "flipkart", "myntra", "meesho"],
        "transportation": ["makemytrip", "google"],
        "return_gifts": ["amazon", "flipkart", "myntra", "meesho"],
        "contingency": ["amazon", "flipkart", "google"]
    }
    default_platforms = ["amazon", "flipkart", "google"]

    total_spent = 0.0
    calc_table = []

    for cat_data in result.get("budget_breakdown", []):
        cat_name = cat_data.get("category", "General").lower()
        relevant_platforms = category_platforms.get(cat_name, default_platforms)
        
        cat_total = 0.0
        cat_items_count = 0

        for item in cat_data.get("items", []):
            qty = int(item.get("quantity", 1))
            price = float(item.get("estimated_price", 0.0))
            item_total = price * qty
            cat_total += item_total
            cat_items_count += qty
            total_spent += item_total

            search_terms = item.get("search_terms") or item.get("name", "")
            encoded_query = urllib.parse.quote_plus(search_terms)

            # Generate platform-specific URLs
            links = {}
            if "amazon" in relevant_platforms:
                links["amazon"] = f"https://www.amazon.in/s?k={encoded_query}"
            if "flipkart" in relevant_platforms:
                links["flipkart"] = f"https://www.flipkart.com/search?q={encoded_query}"
            if "swiggy" in relevant_platforms:
                links["swiggy"] = f"https://www.swiggy.com/search?query={encoded_query}"
            if "zomato" in relevant_platforms:
                links["zomato"] = f"https://www.zomato.com/search?q={encoded_query}"
            if "bigbasket" in relevant_platforms:
                links["bigbasket"] = f"https://www.bigbasket.com/ps/?q={encoded_query}"
            if "bookmyshow" in relevant_platforms:
                links["bookmyshow"] = f"https://in.bookmyshow.com/search?q={encoded_query}"
            if "myntra" in relevant_platforms:
                links["myntra"] = f"https://www.myntra.com/{encoded_query}"
            if "meesho" in relevant_platforms:
                links["meesho"] = f"https://www.meesho.com/search?q={encoded_query}"
            if "google" in relevant_platforms:
                links["google"] = f"https://www.google.com/search?q={encoded_query}"
            if "booking" in relevant_platforms:
                links["booking"] = f"https://www.booking.com/search.html?ss={encoded_query}"
            if "makemytrip" in relevant_platforms:
                links["makemytrip"] = f"https://www.makemytrip.com/hotels/hotel-listing/?searchText={encoded_query}"
            if "oyorooms" in relevant_platforms:
                links["oyorooms"] = f"https://www.oyorooms.com/search/?location={encoded_query}"
            if "nobroker" in relevant_platforms:
                links["nobroker"] = f"https://www.nobroker.in/property/search?searchTerm={encoded_query}"

            item["shopping_links"] = links

        cat_data["allocation"] = round(cat_total, 2)
        pct = round((cat_total / total_budget * 100) if total_budget > 0 else 0, 1)
        calc_table.append({
            "category": cat_name.capitalize(),
            "items_count": cat_items_count,
            "total_cost": round(cat_total, 2),
            "percentage_of_budget": pct
        })

    # Enrich venue suggestions
    venue_platforms = ["google", "booking", "makemytrip", "oyorooms", "nobroker"]
    for venue in result.get("venue_suggestions", []):
        v_terms = venue.get("search_terms") or venue.get("name", "")
        encoded_v = urllib.parse.quote_plus(v_terms)
        venue["search_links"] = {
            "google": f"https://www.google.com/search?q={encoded_v}",
            "booking": f"https://www.booking.com/search.html?ss={encoded_v}",
            "makemytrip": f"https://www.makemytrip.com/hotels/hotel-listing/?searchText={encoded_v}",
            "oyorooms": f"https://www.oyorooms.com/search/?location={encoded_v}",
            "nobroker": f"https://www.nobroker.in/property/search?searchTerm={encoded_v}"
        }

    result["calculation_table_inr"] = calc_table
    result["remaining_budget"] = max(0.0, round(total_budget - total_spent, 2))

    return result


def _fallback_party_recommendations(budget: float, guests: int, p_type: str, v_type: str, catering: bool, decor: bool, entertain: bool) -> dict:
    """Smart fallback generator for party planning."""
    guests = max(guests, 1)
    
    # Budget allocation weights
    w_venue = 0.20 if v_type.lower() != 'home' else 0.05
    w_catering = 0.50 if catering else 0.10
    w_decor = 0.15 if decor else 0.05
    w_entertain = 0.10 if entertain else 0.05
    w_contingency = 0.05

    total_w = w_venue + w_catering + w_decor + w_entertain + w_contingency
    w_venue /= total_w
    w_catering /= total_w
    w_decor /= total_w
    w_entertain /= total_w
    w_contingency /= total_w

    alloc_v = round(budget * w_venue, 2)
    alloc_c = round(budget * w_catering, 2)
    alloc_d = round(budget * w_decor, 2)
    alloc_e = round(budget * w_entertain, 2)
    alloc_cont = round(budget * w_contingency, 2)

    breakdown = [
        {
            "category": "venue",
            "allocation": alloc_v,
            "items": [
                {
                    "name": f"{v_type} Venue Reservation / Cleaning Setup",
                    "description": f"Cozy ambience and seating setup for {guests} guests at {v_type}",
                    "estimated_price": alloc_v,
                    "quantity": 1,
                    "search_terms": f"{v_type} party hall rental for {guests} people"
                }
            ]
        },
        {
            "category": "catering",
            "allocation": alloc_c,
            "items": [
                {
                    "name": f"Gourmet Party Food & Drinks Menu for {guests} guests",
                    "description": f"Appetizers, main dishes, beverages and dessert (approx ₹{round(alloc_c/guests, 1)} per person)",
                    "estimated_price": alloc_c,
                    "quantity": 1,
                    "search_terms": f"Party catering bulk food order {p_type}"
                }
            ]
        },
        {
            "category": "decoration",
            "allocation": alloc_d,
            "items": [
                {
                    "name": f"{p_type} Theme Balloons, Fairy Lights & Backdrop Kit",
                    "description": "Complete DIY party decoration package with photo booth props and streamers",
                    "estimated_price": alloc_d,
                    "quantity": 1,
                    "search_terms": f"{p_type} theme decoration party props kit"
                }
            ]
        },
        {
            "category": "entertainment",
            "allocation": alloc_e,
            "items": [
                {
                    "name": "Party Games Kit, Speaker & Playlist Setup",
                    "description": "Interactive group games, music streaming accessories, and ambient lighting",
                    "estimated_price": alloc_e,
                    "quantity": 1,
                    "search_terms": "Party games board games bluetooth speaker"
                }
            ]
        },
        {
            "category": "contingency",
            "allocation": alloc_cont,
            "items": [
                {
                    "name": "Miscellaneous & Extra Guest Buffer",
                    "description": "Tableware, napkins, ice, disposables, and extra snacks reserve",
                    "estimated_price": alloc_cont,
                    "quantity": 1,
                    "search_terms": "Eco-friendly disposable tableware party pack"
                }
            ]
        }
    ]

    return {
        "total_budget": budget,
        "budget_breakdown": breakdown,
        "venue_suggestions": [
            {
                "name": f"{v_type} Prime Event Spot",
                "type": v_type,
                "capacity": guests,
                "estimated_cost": alloc_v,
                "search_terms": f"{v_type} event booking"
            }
        ],
        "remaining_budget": 0.0,
        "additional_suggestions": [
            "Opt for buffet or family-style service to reduce per-plate costs.",
            "Use digital invitations (WhatsApp / Canva) to save on printing expenses.",
            "Prepare a curated playlist in advance to keep the party energized without extra DJ costs."
        ]
    }


# =====================================================================
# 3. JEWELRY BUDGET RECOMMENDATIONS (MULTIMODAL)
# =====================================================================

def get_jewelry_recommendations(budget_input, image_path: Optional[str] = None) -> dict:
    """Generate jewelry recommendations based on uploaded dress/outfit and budget in INR (multimodal)."""
    total_budget = float(budget_input.total_budget)
    occasion = getattr(budget_input, 'occasion', 'Wedding')
    preferences = getattr(budget_input, 'preferences', None) or "Not specified"

    base_prompt = f"""
I need jewelry recommendations for India with a total budget of ₹{total_budget:.2f}.
Occasion: {occasion}
Preferences: {preferences}
Provide only India-relevant styles, availability, and price ranges in INR.
"""

    image_obj = None
    if image_path and os.path.exists(image_path):
        try:
            image_obj = Image.open(image_path)
        except Exception as e:
            print(f"[WARN] Unable to open image file {image_path}: {e}")
            image_obj = None

    if image_obj:
        prompt = base_prompt + f"""
An image of the outfit is uploaded. Analyze the outfit's colors, neckline, embroidery, silhouette, and formality.
Suggest matching jewelry pieces that complement the outfit aesthetically and fit within the budget of ₹{total_budget:.2f}.

Format the output as JSON:
{{
  "outfit_analysis": {{
    "colors": "Primary and accent colors detected",
    "style": "Traditional / Indo-Western / Contemporary / Formal / Casual",
    "formality": "High / Moderate / Casual"
  }},
  "total_budget": {total_budget:.2f},
  "jewelry_recommendations": [
    {{
      "item_type": "Necklace / Choker / Pendant",
      "description": "Detailed description of the jewelry design and metal finish",
      "style": "Kundan / Polki / Minimalist Gold / Silver Oxidized / Diamond Accent",
      "estimated_price": 0.0,
      "search_terms": "Gold plated kundan choker necklace set"
    }},
    {{
      "item_type": "Earrings / Jhumkas",
      "description": "Matching earrings that frame the face well",
      "style": "Jhumka / Chandbali / Studs / Drop earrings",
      "estimated_price": 0.0,
      "search_terms": "Gold plated chandbali earrings"
    }},
    {{
      "item_type": "Bracelet / Bangles",
      "description": "Wrist accessory complementing the outfit sleeves",
      "style": "Kada / Openable Bangle / Sleek Bracelet",
      "estimated_price": 0.0,
      "search_terms": "Traditional designer kada bangles"
    }},
    {{
      "item_type": "Ring",
      "description": "Statement or minimalist cocktail ring",
      "style": "Adjustable statement ring",
      "estimated_price": 0.0,
      "search_terms": "Adjustable floral statement cocktail ring"
    }}
  ],
  "styling_tips": [
    "Balance the neckline: Pair deep necklines with choker sets and high necks with statement earrings.",
    "Harmonize metal undertones: Match the embroidery zari work (gold, silver, or rose gold) with jewelry tones.",
    "Keep one focal statement piece to maintain sophistication and avoid visual clutter."
  ],
  "remaining_budget": 0.0
}}

Ensure all prices are in INR, items are available on Indian platforms (Amazon, Flipkart, BlueStone, Tanishq, CaratLane, Melorra, Meesho), and sum of prices is within total budget.
"""
    else:
        prompt = base_prompt + f"""
Suggest jewelry pieces that match the occasion ({occasion}) and preferences ({preferences}), staying strictly within ₹{total_budget:.2f}.

Format the output as JSON:
{{
  "total_budget": {total_budget:.2f},
  "jewelry_recommendations": [
    {{
      "item_type": "Necklace",
      "description": "Elegant necklace suited for {occasion}",
      "style": "Contemporary / Ethnic",
      "estimated_price": 0.0,
      "search_terms": "{occasion} designer necklace"
    }},
    {{
      "item_type": "Earrings",
      "description": "Complementary earrings",
      "style": "Drop / Jhumka",
      "estimated_price": 0.0,
      "search_terms": "{occasion} matching earrings"
    }},
    {{
      "item_type": "Bracelet / Bangle",
      "description": "Stylish wrist piece",
      "style": "Classic",
      "estimated_price": 0.0,
      "search_terms": "Designer bracelet {occasion}"
    }}
  ],
  "styling_tips": [
    "Choose jewelry tones that harmonize with your outfit's metallic accents.",
    "Select lightweight pieces for long celebrations to ensure all-day comfort."
  ],
  "remaining_budget": 0.0
}}

Ensure all prices are in INR and relevant to Indian brands (Amazon, Flipkart, BlueStone, Tanishq, CaratLane, Melorra, Meesho).
"""

    result = None
    if gemini_model:
        try:
            if image_obj:
                response = gemini_model.generate_content([prompt, image_obj])
            else:
                response = gemini_model.generate_content(prompt)
            result = extract_json_from_response(response.text)
        except Exception as e:
            print(f"[WARN] Gemini call failed for jewelry recommendations: {e}. Falling back to smart generator.")
            result = None

    if not result or "jewelry_recommendations" not in result:
        result = _fallback_jewelry_recommendations(total_budget, occasion, preferences, has_image=bool(image_obj))

    result["total_budget"] = float(result.get("total_budget", total_budget))

    # Add shopping links for each jewelry item (India-specific)
    total_spent = 0.0
    for item in result.get("jewelry_recommendations", []):
        price = float(item.get("estimated_price", 0.0))
        total_spent += price
        search_terms = item.get("search_terms") or f"{item.get('item_type', '')} {item.get('style', '')}"
        encoded_query = urllib.parse.quote_plus(search_terms)

        item["shopping_links"] = {
            "amazon": f"https://www.amazon.in/s?k={encoded_query}",
            "flipkart": f"https://www.flipkart.com/search?q={encoded_query}",
            "bluestone": f"https://www.bluestone.com/search.html?query={encoded_query}",
            "tanishq": f"https://www.tanishq.co.in/search?q={encoded_query}",
            "caratlane": f"https://www.caratlane.com/search?q={encoded_query}",
            "melorra": f"https://www.melorra.com/search?q={encoded_query}",
            "meesho": f"https://www.meesho.com/search?q={encoded_query}"
        }

    result["remaining_budget"] = max(0.0, round(total_budget - total_spent, 2))
    return result


def _fallback_jewelry_recommendations(budget: float, occasion: str, preferences: str, has_image: bool = False) -> dict:
    """Smart fallback generator for jewelry recommendations."""
    alloc_necklace = round(budget * 0.40, 2)
    alloc_earrings = round(budget * 0.25, 2)
    alloc_bracelet = round(budget * 0.20, 2)
    alloc_ring = round(budget * 0.10, 2)

    items = [
        {
            "item_type": "Necklace / Choker Set",
            "description": f"Exquisite handcrafted choker necklace with matching floral motifs, ideal for {occasion}",
            "style": "Kundan / Rose Gold Plated",
            "estimated_price": alloc_necklace,
            "search_terms": f"Kundan choker necklace set for {occasion}"
        },
        {
            "item_type": "Earrings / Chandbalis",
            "description": "Intricate crescent moon chandbali earrings with delicate pearl drops",
            "style": "Ethnic Pearl Jhumka",
            "estimated_price": alloc_earrings,
            "search_terms": f"Pearl drop chandbali earrings for {occasion}"
        },
        {
            "item_type": "Bracelet / Bangle Set",
            "description": "Adjustable dual-tone sleek bracelet with crystal embellishments",
            "style": "Contemporary Statement Kada",
            "estimated_price": alloc_bracelet,
            "search_terms": f"Designer crystal kada bracelet"
        },
        {
            "item_type": "Statement Ring",
            "description": "Adjustable floral motif cocktail ring with central gemstone setting",
            "style": "Minimalist Festive",
            "estimated_price": alloc_ring,
            "search_terms": f"Statement floral cocktail ring"
        }
    ]

    outfit_analysis = {
        "colors": "Festive Gold & Royal Accents",
        "style": "Traditional / Indo-Western Festive",
        "formality": "High Elegance"
    } if has_image else None

    res = {
        "total_budget": budget,
        "jewelry_recommendations": items,
        "remaining_budget": round(budget * 0.05, 2),
        "styling_tips": [
            f"Coordinate the metal tone of your jewelry with the embroidery and border detailing for {occasion}.",
            "If wearing an elaborate statement necklace, keep the earrings sleek and lightweight.",
            "Layer delicate chain bracelets alongside traditional bangles for a modern chic fusion look."
        ]
    }
    if outfit_analysis:
        res["outfit_analysis"] = outfit_analysis

    return res
