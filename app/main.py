from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os, requests, time

app = FastAPI(title="Astro Backend API")

# CORS allowed origins
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PanchangQuery(BaseModel):
    date: str
    lat: float
    lon: float
    city: str = "Jaipur"

@app.get("/")
def home():
    return {"status": "ok", "msg": "Astro API running on Railway"}

@app.post("/panchang")
def panchang(q: PanchangQuery):
    try:
        return {
            "status": "ok",
            "data": {
                "date": q.date,
                "lat": q.lat,
                "lon": q.lon,
                "city": q.city,
                "tithi": "Pratipada",
                "nakshatra": "Rohini",
                "sunrise": "06:28",
                "sunset": "17:48",
                "note": "Replace with real vedastro or API calc later"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
