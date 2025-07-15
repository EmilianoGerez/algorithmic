from fastapi import FastAPI
from src.api.routes import router as signal_router

app = FastAPI(title="Market Structure Detection")

app.include_router(signal_router, prefix="/detect")
