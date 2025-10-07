from pydantic import BaseModel
from typing import Optional

class CommentCreate(BaseModel):
    content: str

class CommentUpdate(BaseModel):
    content: str

class CommentResponse(BaseModel):
    id: str
    post_id: str
    author_id: str
    content: str
    created_at: str
