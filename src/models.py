"""Pydantic models for API requests and responses."""

from pydantic import BaseModel, Field


# ---------- Response models ----------

class HealthResponse(BaseModel):
    """Response returned by the health check endpoint."""

    status: str
    version: str


class MovieUploadInfo(BaseModel):
    """Summary returned after a movie CSV upload."""

    filename: str
    rows: int
    columns: int
    column_names: list[str]


class MovieDataResponse(BaseModel):
    """Stored movie rows plus the total number of movies."""

    data: list[dict]
    total_rows: int


class MovieProcessingReport(BaseModel):
    """Results of validating and cleaning the stored movies."""

    validation_rows_removed: int
    cleaning_report: dict


# ---------- Request models ----------

class ValidationSettings(BaseModel):
    """Columns that must exist and columns that must be numeric."""

    required_columns: list[str] = Field(default_factory=list)
    numeric_columns: list[str] = Field(default_factory=list)


class MissingSettings(BaseModel):
    """How to handle missing values."""

    enabled: bool = True
    axis: str = "rows"


class OutlierSettings(BaseModel):
    """How to detect and remove outliers."""

    enabled: bool = False
    columns: list[str] = Field(default_factory=list)
    method: str = "iqr"
    threshold: float = 1.5


class ProcessingSettings(BaseModel):
    """All cleaning steps applied after validation."""

    remove_duplicates: bool = True
    missing: MissingSettings = Field(default_factory=MissingSettings)
    outliers: OutlierSettings = Field(default_factory=OutlierSettings)


class ProcessConfig(BaseModel):
    """Full request body for POST /movies/process."""

    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
