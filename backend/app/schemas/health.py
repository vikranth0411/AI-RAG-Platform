from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response body."""

    status: str
