from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./social_studio.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    source_type = Column(String, nullable=False)  # "url" or "markdown"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    variants = relationship("Variant", back_populates="post")


class Variant(Base):
    __tablename__ = "variants"
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    platform = Column(String, nullable=False)  # telegram | mock_x | mock_linkedin
    text = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="draft")  # draft|approved|rejected|published
    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="variants")
    schedule_slots = relationship("ScheduleSlot", back_populates="variant")


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"
    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("variants.id"), nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    idempotency_key = Column(String, unique=True, nullable=False)

    variant = relationship("Variant", back_populates="schedule_slots")
    publish_attempts = relationship("PublishAttempt", back_populates="schedule_slot")


class PublishAttempt(Base):
    __tablename__ = "publish_attempts"
    id = Column(Integer, primary_key=True)
    schedule_slot_id = Column(Integer, ForeignKey("schedule_slots.id"), nullable=False)
    attempted_at = Column(DateTime, default=datetime.utcnow)
    result = Column(String, nullable=False)  # success | failure
    platform_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    schedule_slot = relationship("ScheduleSlot", back_populates="publish_attempts")


def init_db():
    Base.metadata.create_all(bind=engine)