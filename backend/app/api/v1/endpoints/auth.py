from fastapi import APIRouter, status

router = APIRouter()


@router.get("/status", status_code=status.HTTP_200_OK)
def auth_status() -> dict[str, str]:
    return {"module": "auth", "status": "not_implemented"}

