from fastapi import FastAPI
from app.database import create_db_and_tables
from app.routers import auth
from app.routers import sets
from app.routers import rentals


app = FastAPI(title="LEGO Rental Backend")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

app.include_router(auth.router)
app.include_router(sets.router)
app.include_router(rentals.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/demo")
def demo():
    return {"message": "LEGO rental backend demo endpoint"}



