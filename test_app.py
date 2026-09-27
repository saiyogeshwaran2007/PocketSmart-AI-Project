from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_landing_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "PocketSmart" in response.text

def test_login_flow():
    # Test valid credentials for seeded demo user
    response = client.post(
        "/token",
        data={"username": "sai", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    return data["access_token"]

def test_register_flow():
    # Test registering a new user
    response = client.post(
        "/register",
        json={
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "securepassword123",
            "full_name": "Test User"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data

def test_home_planner_endpoint():
    token = test_login_flow()
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post(
        "/generate-home",
        json={
            "total_budget": 50000,
            "num_lights": 5,
            "num_fans": 4,
            "num_furniture": 2,
            "num_dining_tables": 1,
            "rooms": ["Living Room", "Kitchen"],
            "additional_requirements": "Warm modern lighting"
        },
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_budget"] == 50000
    assert "budget_breakdown" in data
    assert "calculation_table" in data
    assert len(data["budget_breakdown"]) > 0
    # Check shopping links exist
    first_item = data["budget_breakdown"][0]["items"][0]
    assert "shopping_links" in first_item
    assert "amazon" in first_item["shopping_links"]
    assert "flipkart" in first_item["shopping_links"]

def test_party_planner_endpoint():
    token = test_login_flow()
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/generate-party",
        json={
            "total_budget": 30000,
            "num_guests": 15,
            "party_type": "Birthday",
            "venue_type": "Home",
            "needs_catering": True,
            "needs_decoration": True,
            "needs_entertainment": True,
            "additional_requirements": "Vegetarian buffet"
        },
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_budget"] == 30000
    assert "budget_breakdown" in data
    assert "calculation_table_inr" in data
    assert len(data["budget_breakdown"]) > 0

def test_jewelry_planner_endpoint():
    token = test_login_flow()
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/generate-jewelry",
        data={
            "total_budget": 20000,
            "occasion": "Wedding",
            "preferences": "Traditional Kundan gold plated"
        },
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_budget"] == 20000
    assert "jewelry_recommendations" in data
    assert len(data["jewelry_recommendations"]) > 0
    first_item = data["jewelry_recommendations"][0]
    assert "shopping_links" in first_item
    assert "tanishq" in first_item["shopping_links"]
    assert "caratlane" in first_item["shopping_links"]

def test_history_endpoint():
    token = test_login_flow()
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/recommendation-history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "history" in data
    assert len(data["history"]) > 0

    # Test detail lookup
    first_id = data["history"][0]["id"]
    detail_res = client.get(f"/recommendation-details/{first_id}", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == first_id

def test_session_endpoints():
    token = test_login_flow()
    headers = {"Authorization": f"Bearer {token}"}

    # Session info
    info_res = client.get("/session-info", headers=headers)
    assert info_res.status_code == 200

    # Session data update
    upd_res = client.post("/session-data", json={"theme": "dark", "currency": "INR"}, headers=headers)
    assert upd_res.status_code == 200
    assert upd_res.json()["data"]["theme"] == "dark"

if __name__ == "__main__":
    print("Running PocketSmart AI automated test suite...")
    test_landing_page()
    print("[PASS] Landing page test")
    test_login_flow()
    print("[PASS] Login & JWT flow test")
    test_register_flow()
    print("[PASS] Registration test")
    test_home_planner_endpoint()
    print("[PASS] Home Interior Planner test")
    test_party_planner_endpoint()
    print("[PASS] Party Budget Planner test")
    test_jewelry_planner_endpoint()
    print("[PASS] Jewelry Budget Planner test")
    test_history_endpoint()
    print("[PASS] Recommendation History & Details test")
    test_session_endpoints()
    print("[PASS] Session info & management test")
    print("\nALL TESTS PASSED SUCCESSFULLY! 100% HEALTHY.")
