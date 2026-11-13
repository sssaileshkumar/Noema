import os
from datetime import datetime, timedelta, timezone

import jwt

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Session, sessionmaker, DeclarativeBase, relationship, joinedload, selectinload

from pydantic import BaseModel, Field, ConfigDict, field_validator

try:
    from pwdlib import PasswordHash
    password_hash = PasswordHash.recommended()
except ImportError:
    from passlib.context import CryptContext
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    class PasswordHash:  # type: ignore
        @staticmethod
        def hash(secret: str) -> str:
            return _pwd_context.hash(secret)

        @staticmethod
        def verify(secret: str, hash: str) -> bool:
            return _pwd_context.verify(secret, hash)

    password_hash = PasswordHash()


engine = create_engine("sqlite:///./database.db", connect_args={"check_same_thread": False})

LocalSession = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass

def get_db():
    db = LocalSession()
    try:
        yield db
    finally:
        db.close()


# ==========================================
# 2. JWT CONFIGURATION
# ==========================================

SECRET_KEY = "CHANGE-THIS-IN-PRODUCTION"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def create_access_token(user_id: int):
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "exp": expire
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def verify_token(token: str) -> int | None:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:
            return None

        return int(user_id)

    except Exception:
        return None


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    tweets = relationship("Tweet", back_populates="author", cascade="all, delete-orphan")

    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan")


class Tweet(Base):
    __tablename__ = "tweets"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False, default="wassup")
    created_at = Column(DateTime, default=datetime.now)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    author = relationship("User", back_populates="tweets")

    likes = relationship("Like", back_populates="tweet", cascade="all, delete-orphan")

    @property
    def username(self) -> str:
        return self.author.username if self.author else ""


class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tweet_id = Column(Integer, ForeignKey("tweets.id"), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "tweet_id"),)

    user = relationship("User", back_populates="likes")
    tweet = relationship("Tweet", back_populates="likes")


class UserForm(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)


class TweetCreate(BaseModel):
    content: str = Field(min_length=1, max_length=280)


class TweetResponse(BaseModel):
    id: int
    username: str
    content: str
    created_at: datetime
    likes: int = 0
    liked_by_me: bool = False

    model_config = ConfigDict(from_attributes=True)

    @field_validator("likes", mode="before")
    @classmethod
    def count_likes(cls, v):
        if isinstance(v, (list, set)):
            return len(v)
        return v


class TweetCreateResponse(BaseModel):
    message: str
    tweet: TweetResponse


class LikeResponse(BaseModel):
    message: str
    liked: bool
    likes: int


Base.metadata.create_all(bind=engine)


app = FastAPI(title="Twitter Clone API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user_id = verify_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user


# Optional authentication for public GET endpoints
optional_oauth2 = OAuth2PasswordBearer(
    tokenUrl="/login",
    auto_error=False
)


def get_optional_user(
    token: str | None = Depends(optional_oauth2),
    db: Session = Depends(get_db)
):

    if not token:
        return None

    user_id = verify_token(token)

    if user_id is None:
        return None

    return db.query(User).filter(
        User.id == user_id
    ).first()


# home
@app.get("/")
def home():
    return {
        "message": "Twitter API is running!"
    }


@app.post("/register")
def register(data: UserForm, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == data.username).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Username already taken"
        )

    new_user = User(username=data.username, password=password_hash.hash(data.password))

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {
            "message": "User registered successfully",
            "username": new_user.username
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Registration failed"
        )


@app.post("/login")
def login(data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()

    if not user or not password_hash.verify(data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = create_access_token(user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@app.post("/tweets", response_model=TweetCreateResponse)
def create_tweet(data: TweetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_tweet = Tweet(content=data.content, user_id=current_user.id)
    new_tweet.author = current_user

    try:
        db.add(new_tweet)
        db.commit()
        db.refresh(new_tweet)

        return {
            "message": "Tweet created successfully",
            "tweet": new_tweet
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create tweet"
        )


@app.get("/tweets", response_model=list[TweetResponse])
def get_tweets(db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    tweets = (
        db.query(Tweet)
        .options(joinedload(Tweet.author), selectinload(Tweet.likes))
        .order_by(Tweet.created_at.desc())
        .all()
    )

    if current_user:
        liked_tweet_ids = {
            row[0]
            for row in db.query(Like.tweet_id)
            .filter(Like.user_id == current_user.id)
            .all()
        }
        for tweet in tweets:
            tweet.liked_by_me = tweet.id in liked_tweet_ids

    return tweets


@app.get("/tweets/{tweet_id}", response_model=TweetResponse)
def get_tweet(tweet_id: int, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_user)):
    tweet = (
        db.query(Tweet)
        .options(joinedload(Tweet.author), selectinload(Tweet.likes))
        .filter(Tweet.id == tweet_id)
        .first()
    )

    if not tweet:
        raise HTTPException(
            status_code=404,
            detail="Tweet not found"
        )

    if current_user:
        tweet.liked_by_me = (
            db.query(Like)
            .filter(Like.user_id == current_user.id, Like.tweet_id == tweet.id)
            .first()
            is not None
        )

    return tweet


@app.post("/tweets/{tweet_id}/like", response_model=LikeResponse)
def like_tweet(tweet_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tweet = db.query(Tweet).filter(Tweet.id == tweet_id).first()

    if not tweet:
        raise HTTPException(
            status_code=404,
            detail="Tweet not found"
        )

    existing_like = db.query(Like).filter(Like.user_id == current_user.id, Like.tweet_id == tweet_id).first()

    if existing_like:
        db.delete(existing_like)
        db.commit()

        return {
            "message": "Tweet unliked successfully",
            "liked": False,
            "likes": len(tweet.likes)
        }

    new_like = Like(user_id=current_user.id, tweet_id=tweet_id)

    try:
        db.add(new_like)
        db.commit()

        return {
            "message": "Tweet liked successfully",
            "liked": True,
            "likes": len(tweet.likes)
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Could not like tweet"
        )
