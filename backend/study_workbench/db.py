from sqlalchemy import JSON, Float, ForeignKey, Integer, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    content: Mapped[dict] = mapped_column(JSON)


class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    response: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(String)


def database(path):
    engine = create_engine("sqlite:///" + path.as_posix(), connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")

    return engine
