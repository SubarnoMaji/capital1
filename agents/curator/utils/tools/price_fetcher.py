from typing import Type, Optional, Any
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
import asyncio
import json

import sys
import os

# Add the parent directory (project root) to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

from usecases.crop_prices.fetcher import CropPriceFetcher
from usecases.crop_prices.utils import *

# Add PrivateAttr import for pydantic v2
from pydantic import PrivateAttr

class PriceFetcherInput(BaseModel):
    commodity: str = Field(..., description="Commodity name, e.g., 'Potato'")
    state: str = Field(..., description="State name, e.g., 'West Bengal'")
    district: Optional[str] = Field(None, description="Optional district name to filter results, e.g., 'Alipurduar'")
    start_date: str = Field(..., description="Start date in format 'DD-Mon-YYYY', e.g., '01-Aug-2025'")
    end_date: str = Field(..., description="End date in format 'DD-Mon-YYYY', e.g., '07-Aug-2025'")

class PriceFetcherTool(BaseTool):
    name: str = "PriceFetcherTool"
    description: str = (
        "Fetch crop price data from Agmarknet via the crop-prices usecase. "
        "Inputs: commodity, state, optional district, start_date, end_date. "
        "Returns a JSON with success flag, data list and total_records or error."
    )
    args_schema: Type[PriceFetcherInput] = PriceFetcherInput

    # Use private attrs to store non-pydantic fields
    _fetcher: Optional[CropPriceFetcher] = PrivateAttr(default=None)
    _init_error: Optional[str] = PrivateAttr(default=None)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        try:
            self._fetcher = CropPriceFetcher()
        except Exception as e:
            self._init_error = str(e)

    async def _arun(self, **kwargs) -> str:
        """Asynchronously fetch crop prices using the underlying fetcher."""
        if self._init_error:
            return json.dumps({
                "success": False,
                "error": f"PriceFetcherTool initialization failed: {self._init_error}"
            })

        commodity = kwargs.get("commodity")
        state = kwargs.get("state")
        district = kwargs.get("district")
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                self._fetcher.fetch_prices,
                commodity,
                state,
                district,
                start_date,
                end_date,
            )
            # Ensure result is JSON serializable string for consistent tool output
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Exception during price fetch: {str(e)}"
            }, ensure_ascii=False)

    def _run(self, **kwargs):
        raise NotImplementedError("Sync version not implemented.") 

if __name__ == "__main__":
    import sys

    async def main():
        # Example test input
        test_input = {
            "commodity": "Potato",
            "state": "West Bengal",
            "district": "Alipurduar",
            "start_date": "01-Aug-2025",
            "end_date": "07-Aug-2025"
        }
        tool = PriceFetcherTool()
        print("Testing PriceFetcherTool with input:")
        print(json.dumps(test_input, indent=2))
        result = await tool._arun(**test_input)
        print("\nResult:")
        print(result)

    asyncio.run(main())