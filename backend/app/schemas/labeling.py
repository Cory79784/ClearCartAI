from pydantic import BaseModel, Field


class LabelingLoadRequest(BaseModel):
    labeler_id: str = "anonymous"
    session_id: str | None = None


class LabelingPointRequest(BaseModel):
    session_id: str
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class LabelingResetRequest(BaseModel):
    session_id: str


class LabelingSkipRequest(BaseModel):
    session_id: str
    labeler_id: str = "anonymous"
    reason: str = "not_clear"


class LabelingSaveRequest(BaseModel):
    session_id: str
    packaging: str = ""
    product_name: str = ""
