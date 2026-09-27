import uvicorn
from app import app

if __name__ == "__main__":
    print("Starting PocketSmart: AI Budget Planner on http://localhost:8000 ...")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
