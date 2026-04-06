from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db_and_tables
from app.routers import auth, sets, rentals, proxy, scan, ai, reviews, friends, users

app = FastAPI(title="LEGO Rental Backend")

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

app.include_router(auth.router)
app.include_router(sets.router)
app.include_router(rentals.router)
app.include_router(proxy.router)
app.include_router(scan.router)
app.include_router(ai.router)
app.include_router(reviews.router)
app.include_router(friends.router)
app.include_router(users.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/demo")
def demo():
    return {"message": "LEGO rental backend demo endpoint"}