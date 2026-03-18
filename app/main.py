"""
MakerCycle Slicer API - Cloud slicing service for 3D print cost estimation.
"""

import asyncio
import os
from dataclasses import asdict

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .slicer import PRUSA_SLICER_BIN, SlicingError, slice_3mf

API_KEY = os.environ.get("API_KEY", "changeme")
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="MakerCycle Slicer",
    version="1.0.0",
    docs_url="/docs",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


def _verify_api_key(request: Request) -> None:
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "makercycle-slicer"}


@app.post("/api/v1/slice")
@limiter.limit("10/minute")
async def slice_model(request: Request, file: UploadFile = File(...)):
    """
    Slice a .3mf file and return print estimates.

    Accepts a multipart/form-data upload with a .3mf file.
    Returns weight, time, and filament data per plate.
    """
    _verify_api_key(request)

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.lower().endswith(".3mf"):
        raise HTTPException(
            status_code=400,
            detail="Only .3mf files are supported",
        )

    # Read file with size limit
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB",
        )

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        result = await slice_3mf(file_bytes, file.filename)
    except SlicingError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Convert dataclass to dict for JSON response
    response = asdict(result)
    response["success"] = True
    return JSONResponse(content=response)
