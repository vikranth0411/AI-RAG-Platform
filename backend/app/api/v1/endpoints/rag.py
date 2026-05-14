from fastapi import APIRouter, status

router = APIRouter()


@router.get("/status", status_code=status.HTTP_200_OK)
def rag_status() -> dict[str, str]:
    return {"module": "rag", "status": "not_implemented"}

