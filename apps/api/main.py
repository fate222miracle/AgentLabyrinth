"""FastAPI entrypoint and routing for AgentLabyrinth M1 Slice B."""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.schemas import (
    CreateEpisodeRequest,
    CreateExperimentRequest,
    EpisodeResponse,
    ErrorResponse,
    ExperimentResponse,
    MetaResponse,
)
from apps.api.service import EpisodeService

app = FastAPI(
    title="AgentLabyrinth API",
    description="Minimal local single-user API for ToolLab Episode execution and trace inspection.",
    version="1.0.0",
)

# Enable CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_default_service = EpisodeService()


def get_episode_service() -> EpisodeService:
    """Dependency provider for EpisodeService."""
    return _default_service


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle schema validation errors without leaking internal path details."""
    req_id = uuid4()
    err = ErrorResponse(
        schema_version="1.0",
        request_id=req_id,
        error_code="VALIDATION_ERROR",
        message="Invalid request payload or prohibited parameter values.",
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=err.model_dump(mode="json"),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle explicit HTTP exceptions with sanitized ErrorResponse structure."""
    req_id = uuid4()
    err = ErrorResponse(
        schema_version="1.0",
        request_id=req_id,
        error_code="REQUEST_FAILED",
        message=str(exc.detail),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=err.model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler preventing system paths or raw upstream leakage."""
    req_id = uuid4()
    err = ErrorResponse(
        schema_version="1.0",
        request_id=req_id,
        error_code="INTERNAL_SERVER_ERROR",
        message="An internal server error occurred while processing the request.",
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=err.model_dump(mode="json"),
    )


@app.get(
    "/api/v1/meta",
    response_model=MetaResponse,
    summary="Get available models, tasks, and system defaults",
)
async def get_meta(
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> MetaResponse:
    """Return available models, tasks, and system default choices."""
    return service.get_meta()


@app.post(
    "/api/v1/episodes",
    response_model=EpisodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute a ToolLab episode and persist its artifact",
)
async def create_episode(
    req: CreateEpisodeRequest,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> EpisodeResponse:
    """Run an episode using the requested model or scenario, saving the resulting trace."""
    try:
        artifact = await service.execute_episode(req)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Episode execution encountered an unexpected runtime failure.",
        ) from exc

    return EpisodeResponse(
        schema_version="1.0",
        request_id=req.request_id,
        artifact=artifact,
    )


@app.get(
    "/api/v1/episodes/{episode_id}",
    response_model=EpisodeResponse,
    summary="Retrieve a previously executed episode by UUID without invoking models",
)
async def get_episode(
    episode_id: UUID,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> EpisodeResponse:
    """Read a saved artifact by its strictly validated UUID."""
    artifact = service.get_episode(episode_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Episode '{episode_id}' not found.",
        )

    return EpisodeResponse(
        schema_version="1.0",
        request_id=uuid4(),
        artifact=artifact,
    )


@app.post(
    "/api/v1/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute a paired comparison experiment (Baseline vs Recovery)",
)
async def create_experiment(
    req: CreateExperimentRequest,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> ExperimentResponse:
    """Run paired episodes serially and return the aggregated ExperimentArtifact."""
    try:
        artifact = await service.execute_experiment(req)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Experiment execution encountered an unexpected runtime failure.",
        ) from exc

    return ExperimentResponse(
        schema_version="1.0",
        request_id=req.request_id,
        experiment=artifact,
    )


@app.get(
    "/api/v1/experiments/{experiment_id}",
    response_model=ExperimentResponse,
    summary="Retrieve a previously executed experiment artifact by UUID",
)
async def get_experiment(
    experiment_id: UUID,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> ExperimentResponse:
    """Read a saved ExperimentArtifact by its strictly validated UUID."""
    artifact = service.get_experiment(experiment_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found.",
        )

    return ExperimentResponse(
        schema_version="1.0",
        request_id=uuid4(),
        experiment=artifact,
    )
