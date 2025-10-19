from functools import wraps
from typing import Annotated

from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine, AsyncSession

from app.config import database_url

engine = create_async_engine(url=database_url)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False,)


def connection(isolation_level=None):
    def decorator(method):
        @wraps(method)
        async def wrapper(*args, **kwargs):
            async with async_session_maker() as session:
                try:
                    # Устанавливаем уровень изоляции, если передан
                    if isolation_level:
                        await session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))

                    # Выполняем декорированный метод
                    return await method(*args, session=session, **kwargs)
                except Exception as e:
                    await session.rollback()  # Откатываем сессию при ошибке
                    raise e  # Поднимаем исключение дальше
                finally:
                    await session.close()  # Закрываем сессию

        return wrapper

    return decorator


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session  # Возвращаем сессию для использования
        except Exception:
            await session.rollback()  # Откатываем транзакцию при ошибке
            raise
        finally:
            await session.close()  # Закрываем сессию


class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True  # Базовый класс будет абстрактным, чтобы не создавать отдельную таблицу для него

    @classmethod
    @property
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + 's'

    def to_dict(self) -> dict:
        # Метод для преобразования объекта в словарь
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
