from datetime import UTC, date, datetime, time

from sqlalchemy import Boolean, DateTime, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from starlette_context import context


def current_user():
    return context.get("user_details")["user_name"]


def time_now():
    return datetime.now(UTC)


SCHEMA = ""  # Default schema for all tables


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(
        String(64), default=current_user, nullable=True
    )
    created_on: Mapped[str] = mapped_column(
        DateTime(timezone=True), default=time_now, nullable=False
    )
    modified_by: Mapped[str] = mapped_column(
        String(64), default=current_user, onupdate=current_user, nullable=True
    )
    modified_on: Mapped[str] = mapped_column(
        DateTime(timezone=True), default=time_now, onupdate=time_now, nullable=False
    )

    def to_dict(self):
        def convert_value(value):
            if isinstance(value, Base):
                return value.to_dict()
            elif isinstance(value, dict):
                return {key: convert_value(val) for key, val in value.items()}
            elif isinstance(value, list):
                return [convert_value(item) for item in value]
            elif isinstance(value, (datetime, date, time)):
                return value.isoformat()
            elif hasattr(value, "to_dict"):
                return convert_value(value.to_dict())
            elif hasattr(value, "__dict__"):
                return convert_value(vars(value))
            return value

        return {
            key: convert_value(value)
            for key, value in self.__dict__.items()
            if not key.startswith(
                "_"
            )  # Exclude private or SQLAlchemy internal attributes
        }