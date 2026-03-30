from fastapi import APIRouter

router = APIRouter()

@router.get("/weekly")
def weekly_report():
    return {
        "success": True,
        "data": {
            "assigned_count": 0,
            "completed_count": 0,
            "overdue_count": 0
        }
    }
