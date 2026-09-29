from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class Defect(BaseModel):
    type: str
    confidence: float = Field(ge=0,le=1,allow_inf_nan=False)
    surface_percent: float | None = Field(default=None,ge=0,le=100)

class Detection(BaseModel):
    model_config=ConfigDict(populate_by_name=True,extra='allow')
    id: int
    class_name: Literal['GOOD','DAMAGED','ROTTEN','SPROUTED','UNDERSIZED','REVIEW_REQUIRED'] = Field(alias='class')
    confidence: float = Field(ge=0,le=1,allow_inf_nan=False)
    bbox: list[float] = Field(min_length=4,max_length=4)
    mask: list[list[float]] | None
    centroid: list[float]
    diameter_mm: float | None = None
    defects: list[Defect] = []
    grade_a_candidate: bool | None = None
    review_required: bool = False
    reasons: list[str] = []

class AnalysisResponse(BaseModel):
    model_config=ConfigDict(extra='allow')
    id: str
    success: bool
    mode: str
    model_version: str
    grading_spec: str
    image_quality: dict
    summary: dict
    grade_a_percentage: float | None
    urs_percentage: float | None
    quality_score: float | None
    review_required: bool
    detections: list[Detection]
