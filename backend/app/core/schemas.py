from hashlib import sha256
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, Field


class ChatInput(BaseModel):
    platform: Literal["web", "dingtalk"] = "web"
    tenant_id: str = Field(default="demo", max_length=200)
    channel_id: str = Field(default="debug", max_length=200)
    user_id: str = Field(default="admin", max_length=200)
    external_id: str = Field(default_factory=lambda: str(uuid4()), max_length=200)
    text: str = Field(min_length=1, max_length=12000)

    def conversation_key(self) -> str:
        import json
        return sha256(json.dumps([self.platform, self.tenant_id, self.channel_id, self.user_id]).encode()).hexdigest()
