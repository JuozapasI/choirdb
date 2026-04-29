from fastapi import APIRouter, Depends, Form, File, UploadFile, Request, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List
import os, re, shutil

from .. import database, models, schemas, auth

# -------------------------
# Utility Functions
# -------------------------

def sanitize_filename(name: str) -> str:
    """Make filename safe by removing spaces and special characters."""
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    return name.strip("_")

def save_pdf_upload(file: UploadFile, dest_dir: str, score_id: int, score_title: str, index: int) -> str:
    """Save PDF with a human-readable filename."""
    title = sanitize_filename(score_title)
    while True:
        filename = f"{score_id}_{title}_{index}.pdf"
        path = os.path.join(dest_dir, filename)
        if not os.path.exists(path):
            break
        index += 1

    with open(path, "wb") as out:
        shutil.copyfileobj(file.file, out)
    return filename

def save_lyrics_upload(file: UploadFile, dest_dir: str, score_id: int, score_title: str, language: str, index: int) -> str:
    """Save lyrics TXT file with language code in the filename."""
    title = sanitize_filename(score_title)
    lang = sanitize_filename(language)
    while True:
        filename = f"{score_id}_{title}_{lang}_{index}.txt"
        path = os.path.join(dest_dir, filename)
        if not os.path.exists(path):
            break
        index += 1

    with open(path, "wb") as out:
        shutil.copyfileobj(file.file, out)
    return filename

# -------------------------
# Directories & Templates
# -------------------------

BASE_UPLOAD = "app/uploads"
PDF_DIR = os.path.join(BASE_UPLOAD, "pdfs")
LYRICS_DIR = os.path.join(BASE_UPLOAD, "lyrics")
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(LYRICS_DIR, exist_ok=True)

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/admin", tags=["admin"])

# -------------------------
# Admin Routes
# -------------------------

@router.get("/", response_class=HTMLResponse)
def admin_home(request: Request, db: Session = Depends(database.get_db),
               current_user: models.User = Depends(auth.admin_required)):
    return templates.TemplateResponse("admin_home.html", {"request": request, "user": current_user})


@router.get("/pending-users", response_class=HTMLResponse)
def pending_users(request: Request, db: Session = Depends(database.get_db),
                  current_user: models.User = Depends(auth.admin_required)):
    users = db.query(models.User).filter(models.User.is_verified == False).all()
    return templates.TemplateResponse("pending_users.html", {"request": request, "users": users, "user": current_user})


@router.post("/verify_user/{user_id}")
def verify_user(user_id: int, make_admin: bool = Form(False), db: Session = Depends(database.get_db),
                current_user: models.User = Depends(auth.admin_required)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return {"error": "User not found"}

    user.is_verified = True
    if make_admin:
        user.role = models.UserRole.ADMIN
    db.commit()
    return RedirectResponse(url="/admin/pending-users", status_code=303)


@router.post("/reject-user/{user_id}")
def reject_user(user_id: int, db: Session = Depends(database.get_db),
                current_user: models.User = Depends(auth.admin_required)):
    user = db.query(models.User).get(user_id)
    if user:
        db.delete(user)
        db.commit()
    return RedirectResponse(url="/admin/pending-users", status_code=303)


@router.get("/users", response_class=HTMLResponse)
def list_users(request: Request, db: Session = Depends(database.get_db),
               current_user: models.User = Depends(auth.admin_required)):
    users = db.query(models.User).all()
    return templates.TemplateResponse("users_list.html", {"request": request, "users": users, "user": current_user})


@router.post("/delete-user/{user_id}")
def delete_user(user_id: int, db: Session = Depends(database.get_db),
                current_user: models.User = Depends(auth.admin_required)):
    user_to_delete = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_to_delete or user_to_delete.role == models.UserRole.ADMIN:
        return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)
    db.delete(user_to_delete)
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


# -------------------------
# Pending Scores Routes
# -------------------------

@router.get("/pending-scores", response_class=HTMLResponse)
def list_pending_scores(request: Request, db: Session = Depends(database.get_db),
                        current_user: models.User = Depends(auth.admin_required)):
    scores = db.query(models.Score).filter(models.Score.status == models.ScoreStatus.PENDING).all()
    return templates.TemplateResponse("pending_scores_list.html", {"request": request, "scores": scores, "user": current_user})


@router.get("/pending-scores/{score_id}", response_class=HTMLResponse)
def pending_score_detail(score_id: int, request: Request, db: Session = Depends(database.get_db),
                         current_user: models.User = Depends(auth.admin_required)):
    score = db.query(models.Score).filter(
        models.Score.id == score_id,
        models.Score.status == models.ScoreStatus.PENDING
    ).first()
    if not score:
        return RedirectResponse(url="/admin/pending-scores")
    return templates.TemplateResponse("pending_score_detail.html", {"request": request, "score": score, "user": current_user})


@router.post("/pending-scores/{score_id}")
async def update_pending_score(
    score_id: int,
    request: Request,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.admin_required),

    # basic fields
    title: str = Form(...),
    composer: Optional[str] = Form(None),
    lyrics_author: Optional[str] = Form(None),
    year: Optional[str] = Form(None),
    voices: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    liturgical_time: Optional[str] = Form(None),
    mass_part: Optional[str] = Form(None),
    parent_issue: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    additional_info: Optional[str] = Form(None),
    archive_id: Optional[str] = Form(None),

    # new files
    new_pdfs: List[UploadFile] = File([]),
    new_lyrics_languages: List[str] = Form([]),
    new_lyrics_files: List[UploadFile] = File([]),

    # deletions
    delete_pdfs: List[int] = Form([]),
    delete_lyrics: List[int] = Form([]),

    # related scores
    related_scores: Optional[List[int]] = Form([]),
    delete_related_scores: Optional[List[int]] = Form([]),

    action: str = Form(...),  # "approve" or "reject"
):
    score = db.query(models.Score).filter(
        models.Score.id == score_id,
        models.Score.status == models.ScoreStatus.PENDING
    ).first()
    if not score:
        return RedirectResponse(url="/admin/pending-scores", status_code=status.HTTP_303_SEE_OTHER)

    form = await request.form()

    # === Update basic fields ===
    for field, value in [
        ("title", title), ("composer", composer), ("lyrics_author", lyrics_author),
        ("year", year), ("voices", voices), ("source", source),
        ("liturgical_time", liturgical_time), ("mass_part", mass_part),
        ("parent_issue", parent_issue), ("tags", tags), ("language", language),
        ("additional_info", additional_info), ("archive_id", archive_id)
    ]:
        setattr(score, field, value)

    # === Delete PDFs ===
    for pdf_id in delete_pdfs:
        pdf = db.query(models.ScorePDF).filter_by(id=pdf_id, score_id=score.id).first()
        if pdf:
            try:
                os.remove(os.path.join(PDF_DIR, pdf.pdf_path))
            except FileNotFoundError:
                pass
            db.delete(pdf)

    # === Delete lyrics ===
    for lyr_id in delete_lyrics:
        lyr = db.query(models.Lyrics).filter_by(id=lyr_id, score_id=score.id).first()
        if lyr:
            try:
                os.remove(os.path.join(LYRICS_DIR, lyr.file_path))
            except FileNotFoundError:
                pass
            db.delete(lyr)

    # === Add new PDFs ===
    pdf_index = len(score.pdfs) + 1
    for up in new_pdfs:
        if up.filename:
            pdf_path = save_pdf_upload(up, PDF_DIR, score.id, score.title, pdf_index)
            db.add(models.ScorePDF(score_id=score.id, pdf_path=pdf_path))
            pdf_index += 1

    # === Add new lyrics ===
    lyr_index = len(score.lyrics) + 1
    for lang, up in zip(new_lyrics_languages, new_lyrics_files):
        if up.filename and lang:
            lyrics_path = save_lyrics_upload(up, LYRICS_DIR, score.id, score.title, lang, lyr_index)
            db.add(models.Lyrics(score_id=score.id, language=lang.strip(), file_path=lyrics_path))
            lyr_index += 1

    # === Update existing lyrics languages ===
    for lyr in score.lyrics:
        new_lang = form.get(f"update_lyrics_languages_{lyr.id}")
        if new_lang and new_lang != lyr.language:
            lyr.language = new_lang

    # === Remove selected related scores (bidirectional) ===
    if delete_related_scores:
        rel_objs = db.query(models.Score).filter(models.Score.id.in_(delete_related_scores)).all()
        for rel in rel_objs:
            if rel in score.related_scores:
                score.related_scores.remove(rel)
            if score in rel.related_scores:
                rel.related_scores.remove(score)

    # === Add new related scores (bidirectional) ===
    if related_scores:
        rel_objs = db.query(models.Score).filter(models.Score.id.in_(related_scores)).all()
        for rel in rel_objs:
            if rel not in score.related_scores:
                score.related_scores.append(rel)
            if score not in rel.related_scores:
                rel.related_scores.append(score)

    # === Handle approve/reject action ===
    if action == "approve":
        score.status = models.ScoreStatus.APPROVED
    elif action == "reject":
        db.delete(score)

    db.commit()
    return RedirectResponse(url="/admin/pending-scores", status_code=status.HTTP_303_SEE_OTHER)

# -------------------------
# Updating Scores Routes
# -------------------------

@router.get("/update/{score_id}", response_class=HTMLResponse)
def update_score_detail(
    score_id: int,
    request: Request,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.admin_required),
):
    score = db.query(models.Score).filter(models.Score.id == score_id).first()
    if not score:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        "update_score.html",
        {
            "request": request,
            "score": score,
            "user": current_user
        }
    )

@router.post("/update/{score_id}")
async def update_score(
    score_id: int,
    request: Request,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.admin_required),

    # basic fields
    title: str = Form(...),
    composer: Optional[str] = Form(None),
    lyrics_author: Optional[str] = Form(None),
    year: Optional[str] = Form(None),
    voices: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    liturgical_time: Optional[str] = Form(None),
    mass_part: Optional[str] = Form(None),
    parent_issue: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    additional_info: Optional[str] = Form(None),
    archive_id: Optional[str] = Form(None),

    # new files
    new_pdfs: List[UploadFile] = File([]),
    new_lyrics_languages: List[str] = Form([]),
    new_lyrics_files: List[UploadFile] = File([]),

    # deletions
    delete_pdfs: List[int] = Form([]),
    delete_lyrics: List[int] = Form([]),

    # related scores
    related_scores: Optional[List[int]] = Form([]),
    delete_related_scores: Optional[List[int]] = Form([]),

    action: str = Form(...),  # "save", "delete", "cancel"
):
    score = db.query(models.Score).filter(models.Score.id == score_id).first()
    if not score:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    # Cancel action
    if action == "cancel":
        return RedirectResponse(url=f"/scores/{score.id}", status_code=status.HTTP_303_SEE_OTHER)

    # Delete action
    if action == "delete":
        for pdf in score.pdfs:
            try:
                os.remove(os.path.join(PDF_DIR, pdf.pdf_path))
            except FileNotFoundError:
                pass
            db.delete(pdf)

        for lyr in score.lyrics:
            try:
                os.remove(os.path.join(LYRICS_DIR, lyr.file_path))
            except FileNotFoundError:
                pass
            db.delete(lyr)

        db.delete(score)
        db.commit()
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    # === Save / Update action ===
    form = await request.form()

    # Update score fields
    for attr, value in [
        ("title", title), ("composer", composer), ("lyrics_author", lyrics_author),
        ("year", year), ("voices", voices), ("source", source), ("liturgical_time", liturgical_time),
        ("mass_part", mass_part), ("parent_issue", parent_issue), ("tags", tags),
        ("language", language), ("additional_info", additional_info), ("archive_id", archive_id)
    ]:
        setattr(score, attr, value)

    # Delete selected PDFs
    for pdf_id in delete_pdfs:
        pdf = db.query(models.ScorePDF).filter_by(id=pdf_id, score_id=score.id).first()
        if pdf:
            try:
                os.remove(os.path.join(PDF_DIR, pdf.pdf_path))
            except FileNotFoundError:
                pass
            db.delete(pdf)

    # Delete selected lyrics
    for lyr_id in delete_lyrics:
        lyr = db.query(models.Lyrics).filter_by(id=lyr_id, score_id=score.id).first()
        if lyr:
            try:
                os.remove(os.path.join(LYRICS_DIR, lyr.file_path))
            except FileNotFoundError:
                pass
            db.delete(lyr)

    # Add new PDFs
    pdf_index = len(score.pdfs) + 1
    for up in new_pdfs:
        if up.filename:
            pdf_path = save_pdf_upload(up, PDF_DIR, score.id, score.title, pdf_index)
            db.add(models.ScorePDF(score_id=score.id, pdf_path=pdf_path))
            pdf_index += 1

    # Add new lyrics
    lyr_index = len(score.lyrics) + 1
    for lang, up in zip(new_lyrics_languages, new_lyrics_files):
        if up.filename and lang:
            lyrics_path = save_lyrics_upload(up, LYRICS_DIR, score.id, score.title, lang, lyr_index)
            db.add(models.Lyrics(score_id=score.id, language=lang.strip(), file_path=lyrics_path))
            lyr_index += 1

    # Update existing lyrics languages
    for lyr in score.lyrics:
        new_lang = form.get(f"update_lyrics_languages_{lyr.id}")
        if new_lang and new_lang != lyr.language:
            lyr.language = new_lang

    # Remove selected related scores (bidirectional)
    if delete_related_scores:
        rel_objs = db.query(models.Score).filter(models.Score.id.in_(delete_related_scores)).all()
        for rel in rel_objs:
            if rel in score.related_scores:
                score.related_scores.remove(rel)
            if score in rel.related_scores:
                rel.related_scores.remove(score)

    # Add new related scores (bidirectional)
    if related_scores:
        rel_objs = db.query(models.Score).filter(models.Score.id.in_(related_scores)).all()
        for rel in rel_objs:
            if rel not in score.related_scores:
                score.related_scores.append(rel)
            if score not in rel.related_scores:
                rel.related_scores.append(score)

    db.commit()
    return RedirectResponse(url=f"/scores/{score.id}", status_code=status.HTTP_303_SEE_OTHER)

# -------------------------
# Updating Score Sets Routes
# -------------------------

@router.get("/sets/update/{set_id}", response_class=HTMLResponse)
def edit_score_set_form(
    set_id: int,
    request: Request,
    current_user: models.User = Depends(auth.admin_required),
    db: Session = Depends(database.get_db)
):
    score_set = db.query(models.ScoreSet).get(set_id)
    if not score_set:
        return RedirectResponse("/scores/sets")
    return templates.TemplateResponse(
        "update_score_set.html",
        {"request": request, "score_set": score_set, "user": current_user}
    )

@router.post("/sets/update/{set_id}")
def edit_score_set(
    set_id: int,
    request: Request,
    title: str = Form(...),
    info: str = Form(None),
    delete_scores: List[int] = Form([]),
    new_scores: List[int] = Form([]),
    action: str = Form(...),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.admin_required)
):
    score_set = db.query(models.ScoreSet).get(set_id)
    if not score_set:
        return RedirectResponse("/scores/sets")

    if action == "delete":
        db.delete(score_set)
        db.commit()
        return RedirectResponse("/scores/sets", status_code=303)

    # Save changes
    score_set.title = title
    score_set.info = info

    # Remove selected scores
    if delete_scores:
        score_set.scores = [s for s in score_set.scores if s.id not in delete_scores]

    # Add new scores
    if new_scores:
        scores_to_add = db.query(models.Score).filter(models.Score.id.in_(new_scores)).all()
        for s in scores_to_add:
            if s not in score_set.scores:
                score_set.scores.append(s)

    db.commit()
    return RedirectResponse(f"/scores/sets/{set_id}", status_code=303)
