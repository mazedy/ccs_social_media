from fastapi import APIRouter
from fastapi import UploadFile, File, Form, HTTPException
from app.core.database import db
from uuid import uuid4
from datetime import datetime
import os
from typing import Optional
from fastapi import Depends
from app.core.security import get_current_user

router = APIRouter(prefix="/posts", tags=["Posts"])

@router.post("/")
async def create_post(
    content: str = Form(...),
    image: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
):
    post_id = str(uuid4())
    created_at = datetime.utcnow().isoformat() + "Z"

    # Ensure uploads directory exists
    uploads_dir = os.path.join(os.getcwd(), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    image_url = None
    if image is not None:
        try:
            # Derive extension from filename, fallback to .bin
            _, ext = os.path.splitext(image.filename or "")
            if not ext:
                ext = ".bin"
            filename = f"{uuid4()}{ext}"
            file_path = os.path.join(uploads_dir, filename)

            with open(file_path, "wb") as f:
                f.write(await image.read())

            # Public URL served via StaticFiles mount at /uploads
            image_url = f"/uploads/{filename}"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save image: {e}")

    with db.get_session() as session:
        session.run(
            """
            MERGE (u:User {id: $author_id})
            CREATE (p:Post {
                id: $id,
                content: $content,
                image_url: $image_url,
                created_at: $created_at
            })
            MERGE (u)-[:AUTHORED]->(p)
            """,
            author_id=current_user["id"],
            id=post_id,
            content=content,
            image_url=image_url,
            created_at=created_at,
        )

    return {
        "id": post_id,
        "content": content,
        "image_url": image_url,
        "created_at": created_at,
    }

@router.get("/")
def get_posts():
    with db.get_session() as session:
        results = session.run("MATCH (p:Post) RETURN p ORDER BY p.created_at DESC")
        # Convert Neo4j Node to plain dict
        return [dict(record["p"]) for record in results]


@router.get("/{post_id}")
def get_post(post_id: str):
    with db.get_session() as session:
        rec = session.run("MATCH (p:Post {id: $id}) RETURN p", id=post_id).single()
        if not rec:
            raise HTTPException(status_code=404, detail="Post not found")
        return dict(rec["p"])


@router.put("/{post_id}")
def update_post(post_id: str, payload: dict, current_user: dict = Depends(get_current_user)):
    # Only author can update
    with db.get_session() as session:
        rel = session.run(
            "MATCH (u:User {id: $uid})-[:AUTHORED]->(p:Post {id: $pid}) RETURN p",
            uid=current_user["id"], pid=post_id,
        ).single()
        if not rel:
            raise HTTPException(status_code=403, detail="Not authorized")
        updates = {}
        if "content" in payload and isinstance(payload["content"], str):
            updates["content"] = payload["content"]
        if not updates:
            return dict(rel["p"])  # nothing to update
        session.run("MATCH (p:Post {id: $id}) SET p += $updates", id=post_id, updates=updates)
        rec = session.run("MATCH (p:Post {id: $id}) RETURN p", id=post_id).single()
        return dict(rec["p"]) if rec else {"id": post_id, **updates}


@router.delete("/{post_id}")
def delete_post(post_id: str, current_user: dict = Depends(get_current_user)):
    with db.get_session() as session:
        rel = session.run(
            "MATCH (u:User {id: $uid})-[:AUTHORED]->(p:Post {id: $pid}) RETURN p",
            uid=current_user["id"], pid=post_id,
        ).single()
        if not rel:
            raise HTTPException(status_code=403, detail="Not authorized")
        session.run("MATCH (p:Post {id: $id}) DETACH DELETE p", id=post_id)
    return {"detail": "Post deleted"}


@router.post("/{post_id}/like")
def like_post(post_id: str, current_user: dict = Depends(get_current_user)):
    with db.get_session() as session:
        exists = session.run("MATCH (p:Post {id: $id}) RETURN p", id=post_id).single()
        if not exists:
            raise HTTPException(status_code=404, detail="Post not found")
        session.run(
            "MATCH (u:User {id: $uid}), (p:Post {id: $pid}) MERGE (u)-[:LIKED]->(p)",
            uid=current_user["id"], pid=post_id,
        )
        count_rec = session.run(
            "MATCH (:User)-[l:LIKED]->(p:Post {id: $pid}) RETURN count(l) as likes",
            pid=post_id,
        ).single()
        return {"post_id": post_id, "likes": count_rec["likes"]}
