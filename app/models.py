from sqlalchemy import Column, Integer, String, Enum, ForeignKey, Text, Boolean, Table
from sqlalchemy.orm import relationship
import enum
from .database import Base

class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"
    
class ScoreStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(Enum(UserRole), default=UserRole.USER)
    is_verified = Column(Boolean, default=False)
    
related_scores_table = Table(
    "related_scores",
    Base.metadata,
    Column("score_id", Integer, ForeignKey("scores.id"), primary_key=True),
    Column("related_score_id", Integer, ForeignKey("scores.id"), primary_key=True),
)

score_set_scores = Table(
    "score_set_scores",
    Base.metadata,
    Column("score_set_id", Integer, ForeignKey("score_sets.id"), primary_key=True),
    Column("score_id", Integer, ForeignKey("scores.id"), primary_key=True)
)

class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    submitted_by_id = Column(Integer, ForeignKey("users.id"))
    submitted_by_username = Column(String)
    title = Column(String, nullable=False)
    composer = Column(String)
    lyrics_author = Column(String)
    year = Column(String)
    voices = Column(Integer, nullable=True)
    source = Column(String)
    liturgical_time = Column(String)
    mass_part = Column(String)
    parent_issue = Column(String)
    tags = Column(String)
    language = Column(String)
    additional_info = Column(Text)
    archive_id = Column(String)
    status = Column(Enum(ScoreStatus), default=ScoreStatus.PENDING)

    # Relationships
    pdfs = relationship("ScorePDF", back_populates="score", cascade="all, delete-orphan")
    lyrics = relationship("Lyrics", back_populates="score", cascade="all, delete-orphan")
    
    related_scores = relationship(
        "Score",
        secondary=related_scores_table,
        primaryjoin=id==related_scores_table.c.score_id,
        secondaryjoin=id==related_scores_table.c.related_score_id,
        back_populates="related_scores"
    )
    
    sets = relationship(
        "ScoreSet",
        secondary=score_set_scores,
        back_populates="scores"
    )
    



class ScorePDF(Base):
    __tablename__ = "score_pdfs"

    id = Column(Integer, primary_key=True, index=True)
    score_id = Column(Integer, ForeignKey("scores.id"))
    pdf_path = Column(String, nullable=False)

    score = relationship("Score", back_populates="pdfs")


class Lyrics(Base):
    __tablename__ = "lyrics"

    id = Column(Integer, primary_key=True, index=True)
    score_id = Column(Integer, ForeignKey("scores.id"))
    language = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # path to txt file

    score = relationship("Score", back_populates="lyrics")
    
class ScoreSet(Base):
    __tablename__ = "score_sets"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    info = Column(Text)
    
    scores = relationship(
        "Score",
        secondary=score_set_scores,
        back_populates="sets"
    )
