from fastapi import FastAPI
from app.database import create_db_and_tables
from app.routers import auth

app = FastAPI(title="LEGO Rental Backend")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

app.include_router(auth.router)



@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/demo")
def demo():
    return {"message": "LEGO rental backend demo endpoint"}



