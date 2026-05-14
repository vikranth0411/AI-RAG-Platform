from fastapi import APIRouter, status

router = APIRouter()


@router.get("/status", status_code=status.HTTP_200_OK)
def files_status() -> dict[str, str]:
    return {"module": "files", "status": "not_implemented"}

