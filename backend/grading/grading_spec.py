from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, model_validator

ROOT = Path(__file__).resolve().parents[2] / 'config'
CLASSES = ('GOOD', 'DAMAGED', 'ROTTEN', 'SPROUTED', 'UNDERSIZED', 'REVIEW_REQUIRED')

class SizeRange(BaseModel):
    min: float = Field(gt=0, allow_inf_nan=False)
    max: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def ordered(self):
        if self.max < self.min:
            raise ValueError('Size maximum must be >= minimum')
        return self

class GradingSpec(BaseModel):
    spec_version: str = Field(min_length=1)
    official: bool = False
    variant: str
    size_range_mm: SizeRange
    review_confidence: float = Field(ge=0, le=1)
    defect_rules: dict[str, Literal['NOT_ALLOWED', 'ALLOWED']]
    tolerances: dict[str, float]
    quality_weights: dict[str, float]
    denominator_policy: Literal['resolved_only'] = 'resolved_only'
    quality: dict[str, float]

    @model_validator(mode='after')
    def weights(self):
        if set(self.quality_weights) != set(CLASSES) - {'REVIEW_REQUIRED'}:
            raise ValueError('Quality weights must define all five resolved classes')
        if any(not 0 <= x <= 100 for x in [*self.quality_weights.values(), *self.tolerances.values()]):
            raise ValueError('Weights and tolerances must be between 0 and 100')
        return self

class URSRules(BaseModel):
    version: str
    enabled: bool = False
    authoritative_source: str | None = None
    classes: list[str] = []
    message: str = 'URS calculation requires the configured official grading specification.'

    @model_validator(mode='after')
    def authoritative(self):
        if self.enabled and (not self.authoritative_source or not self.classes):
            raise ValueError('Enabled URS requires an authoritative source and class definitions')
        if any(c not in CLASSES or c == 'REVIEW_REQUIRED' for c in self.classes) or len(set(self.classes)) != len(self.classes):
            raise ValueError('Invalid or duplicate URS class')
        return self

def load_spec() -> GradingSpec:
    return GradingSpec.model_validate_json((ROOT / 'grading_spec_v1.json').read_text())

def load_urs() -> URSRules:
    return URSRules.model_validate_json((ROOT / 'urs_rules.json').read_text())
