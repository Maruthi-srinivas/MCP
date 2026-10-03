from fastapi import FastAPI
from app.users.service import create_user

app = FastAPI()


@app.post("/users")
def post_users():
    return create_user()
