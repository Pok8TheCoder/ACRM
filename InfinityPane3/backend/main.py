"""
InfinityPane3 Backend — FastAPI
Real-time collaborative timetable canvas connected to ACRM.
"""

import os
import sys

# Add ACRM root to path so we can import routes.database directly
ACRM_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ACRM_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from routers import data, canvas, ws, import_router

app = FastAPI(
    title="InfinityPane3 API",
    description="Real-time collaborative timetable canvas for ACRM",
    version="3.0.0",
)

# CORS — allow Vite dev server (port 5173) and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(data.router, prefix="/api/data", tags=["ACRM Data"])
app.include_router(canvas.router, prefix="/api/canvas", tags=["Canvas"])
app.include_router(import_router.router, prefix="/api/import", tags=["Import"])
app.include_router(ws.router, tags=["WebSocket"])

# Serve React build in production
FRONTEND_BUILD = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(FRONTEND_BUILD):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_BUILD, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_react(full_path: str):
        index = os.path.join(FRONTEND_BUILD, "index.html")
        return FileResponse(index)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "3.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
