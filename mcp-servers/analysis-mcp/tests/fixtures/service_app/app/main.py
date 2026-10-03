from fastapi import FastAPI
from app.users.service import create_user
import httpx

app = FastAPI()


@app.post("/users")
def post_users():
    httpx.get("https://example.test/users")
    return create_user()
