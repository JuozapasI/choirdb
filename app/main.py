from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from . import models, database
from .routers import users, scores, home, admin

# Initialize DB
models.Base.metadata.create_all(bind=database.engine)

# Initialize app and templates
app = FastAPI(title="Choir Database")
templates = Jinja2Templates(directory="app/templates")

# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Handle redirects
    if 300 <= exc.status_code < 400:
        location = exc.headers.get("location") if exc.headers else "/users/login"
        return RedirectResponse(url=location)

    # Handle 404 separately (not found)
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "status_code": 404, "detail": "Puslapis nerastas"},
            status_code=404
        )

    # Default for other HTTP errors
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": exc.status_code, "detail": exc.detail},
        status_code=exc.status_code
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Catch any other unhandled exceptions
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": 500, "detail": str(exc)},
        status_code=500
    )

# Mount static and upload directories
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads/pdfs", StaticFiles(directory="app/uploads/pdfs"), name="pdfs")
app.mount("/uploads/lyrics", StaticFiles(directory="app/uploads/lyrics"), name="lyrics")

# Include routers
app.include_router(users.router)
app.include_router(scores.router)
app.include_router(admin.router)
app.include_router(home.router)

