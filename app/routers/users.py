# app/routers/users.py
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import auth, database, models

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/users", tags=["users"])


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    """Render registration page."""
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
def register_web(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(database.get_db)
):
    """Handle web registration form submission."""
    existing_user = db.query(models.User).filter(models.User.username == username).first()
    if existing_user:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Username already exists"}
        )

    hashed_password = auth.get_password_hash(password)
    db_user = models.User(
        username=username,
        hashed_password=hashed_password,
        role=models.UserRole.USER,  # always USER initially
        is_verified=False            # admin must verify
    )
    db.add(db_user)
    db.commit()

    msg = "Registracija+sėkminga.+Laukiama+administratoriaus+patvirtinimo."
    return RedirectResponse(
        url=f"/users/login?message={msg}",
        status_code=status.HTTP_302_FOUND
    )


@router.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    """API login returning JWT token."""
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="User not verified by admin")
    token = auth.create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, message: Optional[str] = Query(None)):
    """Render login page with optional message."""
    return templates.TemplateResponse("login.html", {"request": request, "message": message})


@router.post("/login")
def login_web(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(database.get_db)
):
    """Handle web login form submission and set JWT cookie."""
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Neteisingi vartotojo vardas arba slaptažodis"},
            status_code=401
        )
    if not user.is_verified:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Nepatvirtintas vartotojas. Paskyra turi būti patvirtinta administratoriaus."},
            status_code=403
        )

    token = auth.create_access_token({"sub": user.username})
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie("access_token", token, httponly=True)
    return response


@router.get("/logout")
def logout():
    """Logout user by deleting JWT cookie."""
    response = RedirectResponse(url="/users/login")
    response.delete_cookie("access_token")
    return response

