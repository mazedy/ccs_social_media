from fastapi import APIRouter, Depends, HTTPException
from uuid import uuid4
from datetime import datetime
from app.core.database import db
from app.core.security import get_current_user
from app.schemas.comment_schema import CommentCreate, CommentUpdate

router = APIRouter(prefix="/comments", tags=["Comments"])


@router.post("/{post_id}")
def create_comment(post_id: str, payload: CommentCreate, current_user: dict = Depends(get_current_user)):
    comment_id = str(uuid4())
    created_at = datetime.utcnow().isoformat() + "Z"
    with db.get_session() as session:
        exists = session.run("MATCH (p:Post {id: $id}) RETURN p", id=post_id).single()
        if not exists:
            raise HTTPException(status_code=404, detail="Post not found")
        session.run(
            """
            MERGE (u:User {id: $uid})
            MATCH (p:Post {id: $pid})
            CREATE (c:Comment {id: $id, content: $content, created_at: $created_at, post_id: $pid, author_id: $uid})
            MERGE (u)-[:AUTHORED]->(c)
            MERGE (c)-[:ON_POST]->(p)
            """,
            uid=current_user["id"], pid=post_id, id=comment_id, content=payload.content, created_at=created_at,
        )
    return {"id": comment_id, "post_id": post_id, "author_id": current_user["id"], "content": payload.content, "created_at": created_at}


@router.get("/post/{post_id}")
def get_comments_for_post(post_id: str):
    with db.get_session() as session:
        results = session.run(
            "MATCH (c:Comment)-[:ON_POST]->(p:Post {id: $pid}) RETURN c ORDER BY c.created_at ASC",
            pid=post_id,
        )
        return [dict(r["c"]) for r in results]


@router.put("/{comment_id}")
def update_comment(comment_id: str, payload: CommentUpdate, current_user: dict = Depends(get_current_user)):
    with db.get_session() as session:
        rel = session.run(
            "MATCH (u:User {id: $uid})-[:AUTHORED]->(c:Comment {id: $cid}) RETURN c",
            uid=current_user["id"], cid=comment_id,
        ).single()
        if not rel:
            raise HTTPException(status_code=403, detail="Not authorized")
        session.run("MATCH (c:Comment {id: $id}) SET c.content = $content", id=comment_id, content=payload.content)
        rec = session.run("MATCH (c:Comment {id: $id}) RETURN c", id=comment_id).single()
        return dict(rec["c"]) if rec else {"id": comment_id, "content": payload.content}


@router.delete("/{comment_id}")
def delete_comment(comment_id: str, current_user: dict = Depends(get_current_user)):
    with db.get_session() as session:
        rel = session.run(
            "MATCH (u:User {id: $uid})-[:AUTHORED]->(c:Comment {id: $cid}) RETURN c",
            uid=current_user["id"], cid=comment_id,
        ).single()
        if not rel:
            raise HTTPException(status_code=403, detail="Not authorized")
        session.run("MATCH (c:Comment {id: $id}) DETACH DELETE c", id=comment_id)
    return {"detail": "Comment deleted"}
