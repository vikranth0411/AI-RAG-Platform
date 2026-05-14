from fastapi import APIRouter, status

router = APIRouter()


@router.get("/status", status_code=status.HTTP_200_OK)
def code_understanding_status() -> dict[str, str]:
    return {"module": "code_understanding", "status": "not_implemented"}

