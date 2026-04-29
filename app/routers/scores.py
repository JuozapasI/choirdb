# app/routers/scores.py
from typing import List, Optional
import os, shutil, re
from fastapi import APIRouter, Depends, Request, Form, File, UploadFile, Query, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_

from .. import models, database, auth

# --- Upload utils ---
def sanitize_filename(name: str) -> str:
    """Make filename safe: remove spaces/special chars."""
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    return name.strip("_")

def save_pdf_upload(file: UploadFile, dest_dir: str, score_id: int, score_title: str, index: int) -> str:
    filename = f"{score_id}_{sanitize_filename(score_title)}_{index}.pdf"
    path = os.path.join(dest_dir, filename)
    with open(path, "wb") as out:
        shutil.copyfileobj(file.file, out)
    return filename

def save_lyrics_upload(file: UploadFile, dest_dir: str, score_id: int, score_title: str, language: str, index: int) -> str:
    filename = f"{score_id}_{sanitize_filename(score_title)}_{sanitize_filename(language)}_{index}.txt"
    path = os.path.join(dest_dir, filename)
    with open(path, "wb") as out:
        shutil.copyfileobj(file.file, out)
    return filename

# --- Directories ---
BASE_UPLOAD = "app/uploads"
PDF_DIR = os.path.join(BASE_UPLOAD, "pdfs")
LYRICS_DIR = os.path.join(BASE_UPLOAD, "lyrics")
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(LYRICS_DIR, exist_ok=True)

# --- Router ---
templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/scores", tags=["Scores"])

# --- routers for score sets ---

@router.get("/sets", response_class=HTMLResponse)
def list_score_sets(request: Request, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    score_sets = db.query(models.ScoreSet).all()
    return templates.TemplateResponse(
        "score_sets_list.html",
        {"request": request, "score_sets": score_sets, "user": current_user}
    )

@router.get("/sets/add", response_class=HTMLResponse)
def add_score_set_form(request: Request, current_user: models.User = Depends(auth.admin_required)):
    return templates.TemplateResponse(
        "add_score_set.html",
        {"request": request, "user": current_user}
    )

@router.post("/sets/add")
def add_score_set(
    request: Request,
    title: str = Form(...),
    info: Optional[str] = Form(None),
    score_ids: List[int] = Form([]),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.admin_required)
):
    existing = db.query(models.ScoreSet).filter_by(title=title).first()
    if existing:
        return templates.TemplateResponse(
            "score_set_add.html",
            {"request": request, "user": current_user, "error": "Rinkinys su tokiu pavadinimu jau egzistuoja"}
        )

    new_set = models.ScoreSet(title=title, info=info)
    if score_ids:
        scores = db.query(models.Score).filter(models.Score.id.in_(score_ids)).all()
        new_set.scores.extend(scores)

    db.add(new_set)
    db.commit()
    return RedirectResponse(url="/scores/sets", status_code=303)

@router.get("/sets/{set_id}", response_class=HTMLResponse)
def set_preview(
    set_id: int,
    request: Request,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    set_obj = db.query(models.ScoreSet).filter(models.ScoreSet.id == set_id).first()
    if not set_obj:
        raise HTTPException(status_code=404, detail="Set not found")
    
    scores = sorted(set_obj.scores, key=lambda s: s.title or "")

    return templates.TemplateResponse(
        "score_set_detail.html",
        {
            "request": request,
            "scores": scores,
            "set": set_obj,
            "user": current_user,
            "title": set_obj.title,
            "info": set_obj.info,
        }
    )

# --- routers for scores ---

@router.get("/", response_class=HTMLResponse)
def home(request: Request, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    scores = db.query(models.Score).all()
    return templates.TemplateResponse("scores_list.html", {"request": request, "scores": scores, "user": current_user})


@router.get("/add", response_class=HTMLResponse)
def add_score_form(request: Request, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Render the add score form with existing approved scores for related selection."""
    existing_scores = db.query(models.Score).filter(models.Score.status == models.ScoreStatus.APPROVED).order_by(models.Score.title.asc()).all()
    return templates.TemplateResponse("add_score.html", {"request": request, "user": current_user, "existing_scores": existing_scores})


@router.post("/add")
async def add_score(
    request: Request,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),

    # core fields
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

    # relationships
    related_scores: List[int] = Form([]),

    # files
    pdf_files: List[UploadFile] = File([]),
    lyrics_languages: List[str] = Form([]),
    lyrics_files: List[UploadFile] = File([]),
):
    """Handle adding a new score with files and relationships."""
    score = models.Score(
        submitted_by_id=current_user.id,
        submitted_by_username=current_user.username,
        title=title,
        composer=composer,
        lyrics_author=lyrics_author,
        year=year,
        voices=voices,
        source=source,
        liturgical_time=liturgical_time,
        mass_part=mass_part,
        parent_issue=parent_issue,
        tags=tags,
        language=language,
        additional_info=additional_info,
        archive_id=archive_id,
        status=models.ScoreStatus.APPROVED if current_user.role == models.UserRole.ADMIN else models.ScoreStatus.PENDING,
    )
    db.add(score)
    db.flush()  # assign ID

    # related scores
    if related_scores:
        rel_objs = db.query(models.Score).filter(models.Score.id.in_(related_scores)).all()
        for rel in rel_objs:
            if rel not in score.related_scores:
                score.related_scores.append(rel)
            if score not in rel.related_scores:
                rel.related_scores.append(score)

    # save PDFs
    for i, pdf in enumerate(pdf_files, start=1):
        if pdf.filename:
            pdf_path = save_pdf_upload(pdf, PDF_DIR, score.id, score.title, i)
            db.add(models.ScorePDF(score_id=score.id, pdf_path=pdf_path))

    # save lyrics
    for i in range(len(lyrics_files)):
        pdf = lyrics_files[i]
        lang = lyrics_languages[i] if i < len(lyrics_languages) else None
        if pdf.filename and lang:
            path = save_lyrics_upload(pdf, LYRICS_DIR, score.id, score.title, lang, i+1)
            db.add(models.Lyrics(score_id=score.id, language=lang.strip(), file_path=path))

    db.commit()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/search_light")
def search_light(q: str = Query(..., min_length=1), db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    results = db.query(models.Score).filter(models.Score.title.ilike(f"%{q}%")).limit(10).all()
    return [{"id": s.id, "title": s.title, "composer": s.composer, "voices": s.voices} for s in results]


@router.get("/search")
def search_scores(
    request: Request,
    q: Optional[str] = None,
    title: Optional[str] = None,
    composer: Optional[str] = None,
    lyrics_author: Optional[str] = None,
    liturgical_time: Optional[str] = None,
    mass_part: Optional[str] = None,
    language: Optional[str] = None,
    voices_min: Optional[str] = None,
    voices_max: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # dropdown values
    liturgical_times = [row[0] for row in db.query(models.Score.liturgical_time).distinct()]
    mass_parts = [row[0] for row in db.query(models.Score.mass_part).distinct()]
    languages = [row[0] for row in db.query(models.Score.language).distinct()]

    query = db.query(models.Score)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                models.Score.title.ilike(like),
                models.Score.composer.ilike(like),
                models.Score.lyrics_author.ilike(like),
                models.Score.language.ilike(like),
                models.Score.source.ilike(like),
                models.Score.liturgical_time.ilike(like),
                models.Score.mass_part.ilike(like),
                models.Score.tags.ilike(like),
                models.Score.parent_issue.ilike(like),
                models.Score.additional_info.ilike(like),
                models.Score.archive_id.ilike(like),
            )
        )

    if title:
        query = query.filter(models.Score.title.ilike(f"%{title}%"))
    if composer:
        query = query.filter(models.Score.composer.ilike(f"%{composer}%"))
    if lyrics_author:
        query = query.filter(models.Score.lyrics_author.ilike(f"%{lyrics_author}%"))
    if liturgical_time:
        query = query.filter(models.Score.liturgical_time == liturgical_time)
    if mass_part:
        query = query.filter(models.Score.mass_part == mass_part)
    if language:
        query = query.filter(models.Score.language == language)
    if voices_min and voices_min.isdigit():
        query = query.filter(models.Score.voices >= int(voices_min))
    if voices_max and voices_max.isdigit():
        query = query.filter(models.Score.voices <= int(voices_max))

    scores = query.all()

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "scores": scores,
            "user": current_user,
            "liturgical_times": liturgical_times,
            "mass_parts": mass_parts,
            "languages": languages,
            "voices_min": voices_min,
            "voices_max": voices_max,
        },
    )


@router.get("/{score_id}", response_class=HTMLResponse)
def score_detail(score_id: int, request: Request, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    score = db.query(models.Score).filter(models.Score.id == score_id).first()
    if not score:
        raise HTTPException(status_code=404, detail="Score not found")
    return templates.TemplateResponse("score_detail.html", {"request": request, "score": score, "user": current_user})
