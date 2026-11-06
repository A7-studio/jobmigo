import uuid

from pydantic import BaseModel


class StaffInfo(BaseModel):
    role: str
    permissions: list[str]


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    locale: str
    timezone: str
    staff: StaffInfo | None
