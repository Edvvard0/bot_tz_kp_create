import enum
from datetime import datetime

from pydantic import BaseModel

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


class TaskOut(BaseModel):
    id: int
    title: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_mapping(cls, m: dict) -> "TaskOut":
        from datetime import datetime
        data = dict(m)
        # status → русское
        s = data.get("status")
        if isinstance(s, str):
            try:
                data["status"] = ProjectStatus(s).value
            except Exception:
                data["status"] = s
        # даты → ДД.ММ.ГГГГ ЧЧ:ММ
        def fmt(dt):
            if not dt:
                return None
            if isinstance(dt, str):
                try:
                    dt = datetime.fromisoformat(dt)
                except Exception:
                    return dt
            return dt.strftime("%d.%m.%Y %H:%M")
        data["created_at"] = fmt(data.get("created_at"))
        data["updated_at"] = fmt(data.get("updated_at"))
        return cls(**data)