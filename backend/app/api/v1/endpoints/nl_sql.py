from fastapi import APIRouter, status

router = APIRouter()


@router.get("/status", status_code=status.HTTP_200_OK)
def nl_sql_status() -> dict[str, str]:
    return {"module": "nl_sql", "status": "not_implemented"}

