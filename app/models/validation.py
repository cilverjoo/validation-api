from typing import List

from pydantic import BaseModel, Field


class GtError(BaseModel):
    message: str
    richMessage: str
    is_warning: bool = False


class AnnotationError(GtError):
    annotationId: str = None
    annotationType: str = None
    description: str


class GtErrorResponse(BaseModel):
    warnings: List[GtError]
    errors: List[GtError]


class AnnotationErrorResponse(BaseModel):
    warnings: List[AnnotationError]
    errors: List[AnnotationError]


class ValidationUrlModel(BaseModel):
    year: int = Field(gt=2022, lt=2030)
    customer: str = Field(min_length=1, max_length=20)
    project: str = Field(min_length=1, max_length=20)
    version: int = Field(gt=0, lt=20)



class ValidationModel(BaseModel):
    success: bool = False
    annotationErrors: AnnotationErrorResponse = AnnotationErrorResponse(warnings=[], errors=[])
    globalErrors: GtErrorResponse = GtErrorResponse(warnings=[], errors=[])
