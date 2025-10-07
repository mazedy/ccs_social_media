from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes import auth, users, posts, chat, comments
import os

app = FastAPI(title="College Social Media Backend")

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(chat.router)
app.include_router(comments.router)

@app.get("/")
def root():
    return {"message": "Welcome to College Social Media Backend!"}

@app.get("/health")
def health():
    return {"status": "ok"}

# Add this for Render deployment
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)