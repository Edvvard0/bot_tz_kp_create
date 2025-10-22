from __future__ import annotations
from datetime import datetime, timezone
import enum
from typing import Optional, List

from select import select
from sqlalchemy import String, Integer, DateTime, Enum as SAEnum, func, desc, literal_column, text, BigInteger, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.base import BaseDAO
from app.db.schemas.tasks import TaskOut

from datetime import datetime
import pytz

def moscow_now():
    return datetime.now(pytz.timezone('Europe/Moscow'))


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
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(
        SAEnum(
            ProjectStatus,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            native_enum=False,
        ),
        default=ProjectStatus.new.value,
        nullable=False,
    )

    # 🔹 Новые поля
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # tg id инициатора (бизнес/team)
    brief_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=moscow_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=moscow_now,
                                                 onupdate=moscow_now, nullable=False)

class TaskDAO(BaseDAO):
    model = Task

    # --- ЧИСТЫЕ SQL: COUNT ---
    @classmethod
    async def count_all(cls, session: AsyncSession) -> int:
        """
        Возвращает общее количество проектов.
        """
        # Если имя таблицы вдруг кастомное — можно подставить Task.__tablename__
        sql = text("SELECT COUNT(*) AS cnt FROM tasks;")
        res = await session.execute(sql)
        return int(res.scalar_one())

    # --- ЧИСТЫЕ SQL: получить 1 по смещению (сорян. от новых к старым) ---
    @classmethod
    async def get_by_offset_desc(cls, session: AsyncSession, offset: int) -> Optional[TaskOut]:
        """
        Возвращает проект по смещению, сортируя от новых к старым.
        """
        sql = text("""
            SELECT id, title, status, created_at, updated_at
            FROM tasks
            ORDER BY created_at DESC NULLS LAST, id DESC
            OFFSET :offset
            LIMIT 1
        """)
        res = await session.execute(sql, {"offset": int(offset)})
        row = res.mappings().first()
        return TaskOut.from_mapping(row) if row else None

    # --- ЧИСТЫЕ SQL: страница задач (на будущее, для списков) ---
    @classmethod
    async def list_page_desc(cls, session: AsyncSession, *, offset: int = 0, limit: int = 10) -> List[TaskOut]:
        sql = text("""
            SELECT id, title, status, created_at, updated_at
            FROM tasks
            ORDER BY created_at DESC NULLS LAST, id DESC
            OFFSET :offset
            LIMIT :limit
        """)
        res = await session.execute(sql, {"offset": int(offset), "limit": int(limit)})
        rows = res.mappings().all()
        return [TaskOut.from_mapping(r) for r in rows]

    @classmethod
    async def get_out_by_id(cls, session: AsyncSession, task_id: int) -> Optional[TaskOut]:
        sql = text(f"""
               SELECT id, title, status, created_at, updated_at
               FROM {cls.model}
               WHERE id = :id
           """)
        row = (await session.execute(sql, {"id": int(task_id)})).mappings().first()
        return TaskOut.from_mapping(row) if row else None