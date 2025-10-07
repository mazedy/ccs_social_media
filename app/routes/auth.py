from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from app.schemas.user_schema import UserCreate, UserLogin
from app.core.security import get_password_hash, verify_password, create_access_token, get_current_user
from app.core.database import db
from uuid import uuid4

router = APIRouter(prefix="/auth", tags=["Auth"])

# -------------------- REGISTER --------------------
@router.post("/register")
def register(user: UserCreate):
    with db.get_session() as session:
        result = session.run("MATCH (u:User {email: $email}) RETURN u", email=user.email)
        if result.single():
            raise HTTPException(status_code=400, detail="Email already registered")

        user_id = str(uuid4())
        hashed_pw = get_password_hash(user.password)
        session.run(
            "CREATE (u:User {id: $id, username: $username, email: $email, password: $password})",
            id=user_id, username=user.username, email=user.email, password=hashed_pw
        )
    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}


# -------------------- LOGIN (OAuth2 popup compatible) --------------------
@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Supports OAuth2 popup (form-data)."""
    identifier = form_data.username
    password = form_data.password

    if not identifier or not password:
        raise HTTPException(status_code=400, detail="Username/email and password required")

    with db.get_session() as session:
        record = session.run("""
            MATCH (u:User)
            WHERE u.email = $id OR u.username = $id
            RETURN u
        """, id=identifier).single()

        if not record:
            raise HTTPException(status_code=400, detail="Invalid credentials")

        u = record["u"]
        if not verify_password(password, u["password"]):
            raise HTTPException(status_code=400, detail="Invalid password")

    token = create_access_token({"sub": identifier})
    return {"access_token": token, "token_type": "bearer"}


# -------------------- LOGIN WITH USERNAME (JSON only) --------------------
@router.post("/login-with-username")
def login_with_username(payload: dict):
    """Login using JSON body: {"username": "...", "password": "..."}"""
    username = payload.get("username")
    password = payload.get("password")

    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    with db.get_session() as session:
        record = session.run("MATCH (u:User {username: $username}) RETURN u", username=username).single()
        if not record:
            raise HTTPException(status_code=400, detail="Invalid credentials")

        u = record["u"]
        if not verify_password(password, u["password"]):
            raise HTTPException(status_code=400, detail="Invalid password")

    token = create_access_token({"sub": username})
    return {"access_token": token, "token_type": "bearer"}


# -------------------- USER LIST --------------------
@router.get("/users")
def list_users(current_user: dict = Depends(get_current_user)):
    with db.get_session() as session:
        results = session.run("MATCH (u:User) RETURN u ORDER BY u.username")
        out = []
        for r in results:
            u = dict(r["u"])
            u.pop("password", None)
            out.append(u)
        return out


@router.delete("/delete-user")
def delete_user(user_id: str):
    """Delete a user by ID"""
    with db.get_session() as session:
        result = session.run(
            "MATCH (u:User {id: $user_id}) DETACH DELETE u RETURN count(u) AS deleted_count",
            user_id=user_id
        ).single()

        if result["deleted_count"] == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id '{user_id}' not found."
            )

    return {"detail": "User deleted"}