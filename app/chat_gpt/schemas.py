from pydantic import BaseModel, Field

class GptPostResponse(BaseModel):
    title: str = Field(..., max_length=255)
    tg_post: str = Field(..., min_length=20, max_length=2000)