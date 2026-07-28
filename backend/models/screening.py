from pydantic import BaseModel


class ScreeningResult(BaseModel):
    decision: str
    reason: str