from pydantic import BaseModel, validator
from enum import Enum
from typing import Optional, List

class UserRole(str, Enum):
    admin = "admin"
    user = "user"

class UserCreate(BaseModel):
    username: str
    password: str
    role: Optional[UserRole] = UserRole.user

class UserLogin(BaseModel):
    username: str
    password: str
    
class ScorePDFBase(BaseModel):
    pdf_path: str

class ScorePDFCreate(ScorePDFBase):
    pass

class ScorePDFOut(ScorePDFBase):
    id: int
    model_config = {
        "from_attributes": True
    }


class LyricsBase(BaseModel):
    language: str
    file_path: str

class LyricsCreate(LyricsBase):
    pass

class LyricsOut(LyricsBase):
    id: int
    model_config = {
        "from_attributes": True
    }


# --- Main Score schemas ---
class ScoreBase(BaseModel):
    title: str
    composer: Optional[str] = None
    lyrics_author: Optional[str] = None
    year: Optional[str] = None
    voices: Optional[int] = None
    source: Optional[str] = None
    liturgical_time: Optional[str] = None
    mass_part: Optional[str] = None
    parent_issue: Optional[str] = None
    tags: Optional[str] = None
    language: Optional[str] = None
    additional_info: Optional[str] = None
    archive_id: Optional[str] = None
    
    @validator("voices", pre=True)
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v


class ScoreCreate(ScoreBase):
    pdfs: List[ScorePDFCreate] = []
    lyrics: List[LyricsCreate] = []
    related_score_ids: List[int] = []   # IDs of related scores


class ScoreOut(ScoreBase):
    id: int
    status: str
    submitted_by_id: int

    pdfs: List[ScorePDFOut] = []
    lyrics: List[LyricsOut] = []
    related_scores: List["ScoreOutShort"] = []

    model_config = {
        "from_attributes": True
    }


class ScoreOutShort(BaseModel):
    id: int
    title: str
    model_config = {
        "from_attributes": True
    }




