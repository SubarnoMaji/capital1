from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import uvicorn
import os
from fetcher import CropPriceFetcher

class PriceRequest(BaseModel):
    commodity: str = Field(..., description="Commodity name (e.g., 'Potato')")
    state: str = Field(..., description="State name (e.g., 'West Bengal')")
    district: Optional[str] = Field(None, description="District name (optional)")
    start_date: str = Field(..., description="Start date (e.g., '01-Aug-2025')")
    end_date: str = Field(..., description="End date (e.g., '07-Aug-2025')")

app = FastAPI(
    title="Crop Prices API",
    description="API for fetching crop prices from Agmarknet",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scraper = CropPriceFetcher()

@app.post("/fetch-prices")
async def fetch_prices(payload: PriceRequest):
    result = scraper.fetch_prices(
        commodity=payload.commodity,
        state=payload.state,
        district=payload.district,
        start_date=payload.start_date,
        end_date=payload.end_date
    )
    if not result.get("success", False):
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return result

@app.get("/health")
async def health():
    return {"status": "ok"}
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)