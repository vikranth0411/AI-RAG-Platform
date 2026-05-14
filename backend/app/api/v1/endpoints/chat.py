from fastapi import APIRouter, status

router = APIRouter()


@router.get("/status", status_code=status.HTTP_200_OK)
def chat_status() -> dict[str, str]:
    return {"module": "chat", "status": "not_implemented"}

