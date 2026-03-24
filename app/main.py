from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import create_db_and_tables
from app.routers import auth, sets, rentals
from app.routers import proxy


app = FastAPI(title="LEGO Rental Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/demo")
def demo():
    return {"message": "LEGO rental backend demo endpoint"}



