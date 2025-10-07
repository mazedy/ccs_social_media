from fastapi import APIRouter, Depends, HTTPException
from app.core.database import db
from app.core.security import get_current_user
from app.schemas.user_schema import UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.put("/me")
def update_me(payload: UserUpdate, current_user: dict = Depends(get_current_user)):
    updates = {}
    if payload.bio is not None:
        updates["bio"] = payload.bio
    if payload.profile_pic is not None:
        updates["profile_pic"] = payload.profile_pic
    if not updates:
        return current_user
    with db.get_session() as session:
        session.run(
            "MATCH (u:User {id: $id}) SET u += $updates RETURN u",
            id=current_user["id"], updates=updates,
        )
        rec = session.run("MATCH (u:User {id: $id}) RETURN u", id=current_user["id"]).single()
        if not rec:
            raise HTTPException(status_code=404, detail="User not found")
        u = dict(rec["u"])
        u.pop("password", None)
        return u


@router.get("/{user_id}")
def get_user_by_id(user_id: str):
    with db.get_session() as session:
        rec = session.run("MATCH (u:User {id: $id}) RETURN u", id=user_id).single()
        if not rec:
            raise HTTPException(status_code=404, detail="User not found")
        u = dict(rec["u"])
        u.pop("password", None)
        return u


@router.post("/{user_id}/follow")
def follow_user(user_id: str, current_user: dict = Depends(get_current_user)):
    with db.get_session() as session:
        session.run(
            "MATCH (me:User {id: $me}), (u:User {id: $uid}) MERGE (me)-[:FOLLOWS]->(u)",
            me=current_user["id"], uid=user_id,
        )
    return {"detail": "Followed"}


@router.post("/{user_id}/unfollow")
def unfollow_user(user_id: str, current_user: dict = Depends(get_current_user)):
    with db.get_session() as session:
        session.run(
            "MATCH (me:User {id: $me})-[r:FOLLOWS]->(u:User {id: $uid}) DELETE r",
            me=current_user["id"], uid=user_id,
        )
    return {"detail": "Unfollowed"}


@router.get("/me/feed")
def get_my_feed(current_user: dict = Depends(get_current_user)):
    with db.get_session() as session:
        results = session.run(
            """
            MATCH (me:User {id: $me})-[:FOLLOWS]->(u:User)-[:AUTHORED]->(p:Post)
            RETURN p ORDER BY p.created_at DESC
            """,
            me=current_user["id"],
        )
        posts = [dict(r["p"]) for r in results]
        return posts


@router.get("/search/{query}")
def search_users(query: str):
    with db.get_session() as session:
        results = session.run(
            "MATCH (u:User) WHERE toLower(u.username) CONTAINS toLower($q) OR toLower(u.email) CONTAINS toLower($q) RETURN u LIMIT 50",
            q=query,
        )
        out = []
        for r in results:
            u = dict(r["u"])
            u.pop("password", None)
            out.append(u)
        return out
