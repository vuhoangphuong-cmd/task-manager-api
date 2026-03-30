from pydantic import BaseModel

class AssistantCommandRequest(BaseModel):
    actor_user_id: str
    message: str
