from __future__ import annotations
from datetime import datetime
import enum

from sqlalchemy import String, Integer, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.base import BaseDAO


class ProjectStatus(str, enum.Enum):
    new = "новый"                       # только что создан
    drafting_tz_kp = "составляется тз/кп"  # составляется ТЗ/КП
    sourcing_devs = "ищем разработчиков"
    selecting_devs = "выбираем разработчиков"
    send_tz_to_client = "высылаем тз заказчику"
    create_group = "создаём группу"
    in_dev = "в разработке"
    done = "готово"
    cancelled = "отменён"


class Task(Base):
    """
    В нашем контексте Task == Project.
    Храним только то, что нужно для MVP: название, статус, даты.
    """
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(SAEnum(ProjectStatus), default=ProjectStatus.new, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow,
                                                 onupdate=datetime.utcnow, nullable=False)


class TaskDAO(BaseDAO):
    model = Task
