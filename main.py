"""FastAPI application for storing, querying, and processing movies."""

import io
import logging

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from data_pipeline import create_cleaning_report, process_data, validate_dataframe
from src import (
    HealthResponse,
    MovieDataResponse,
    MovieProcessingReport,
    MovieStorage,
    MovieUploadInfo,
    ProcessConfig,
    log_requests,
    setup_logging,
)
from src.storage import MOVIE_COLUMNS

setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Movie API", version="1.0.0")
app.middleware("http")(log_requests)

storage = MovieStorage()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {"status": "ok", "version": app.version}


@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    """Upload a movie CSV and replace the stored collection."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        logger.warning("Rejected upload with unsupported extension: %s", file.filename)
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as error:
        logger.warning("Could not parse CSV %s: %s", file.filename, error)
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {error}") from error

    if sorted(df.columns) != sorted(MOVIE_COLUMNS):
        logger.warning("Wrong columns in %s: %s", file.filename, list(df.columns))
        raise HTTPException(
            status_code=400,
            detail=f"CSV must have exactly these columns: {', '.join(MOVIE_COLUMNS)}",
        )
    if df.empty:
        logger.warning("Uploaded CSV has no data rows: %s", file.filename)
        raise HTTPException(status_code=400, detail="CSV must contain at least one data row")

    df = df[MOVIE_COLUMNS]
    storage.save(df)
    logger.info("Uploaded movies: filename=%s, rows=%d", file.filename, len(df))

    return {
        "filename": file.filename,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
    }


@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    """Return up to limit stored movies and the total movie count."""
    data = storage.select_columns(MOVIE_COLUMNS, limit)
    total_rows = storage.count_movies()
    logger.info("Retrieved movies: returned_rows=%d", len(data))
    return {"data": data, "total_rows": total_rows}


@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1),
):
    """Return selected fields for movies at or above min_rating."""
    try:
        results = storage.query_movies(columns, min_rating, limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    logger.info(
        "Queried movies: columns=%s, min_rating=%s, returned_rows=%d",
        columns, min_rating, len(results),
    )
    return results


@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    """Validate and clean the stored movies using MP1 functions."""
    df = storage.get()
    if df.empty:
        logger.warning("Process requested with no stored movies")
        raise HTTPException(status_code=400, detail="No movies stored; upload a CSV first")

    config_dict = config.model_dump()
    required_columns = config_dict["validation"]["required_columns"]
    numeric_columns = config_dict["validation"]["numeric_columns"]

    missing_numeric = [col for col in numeric_columns if col not in df.columns]
    if missing_numeric:
        logger.warning("Numeric column(s) not found: %s", missing_numeric)
        raise HTTPException(
            status_code=400,
            detail=f"Numeric column(s) not found: {', '.join(missing_numeric)}",
        )

    try:
        rows_before_validation = len(df)
        validated = validate_dataframe(df, required_columns, numeric_columns)
        validation_removed = rows_before_validation - len(validated)
        validated_copy = validated.copy()

        processed = process_data(validated, config_dict)
    except ValueError as error:
        logger.warning("Processing failed: %s", error)
        raise HTTPException(status_code=400, detail=str(error)) from error

    report = create_cleaning_report(validated_copy, processed)
    storage.save(processed)

    logger.info(
        "Processed movies: validation_removed=%d, rows_before=%d, rows_after=%d",
        validation_removed, report["rows_before"], report["rows_after"],
    )
    return {"validation_rows_removed": validation_removed, "cleaning_report": report}
