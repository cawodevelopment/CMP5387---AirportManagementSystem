from __future__ import annotations

import os
from datetime import datetime
from typing import Any, TypeAlias

import bcrypt
from flasgger import Swagger
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt,
    jwt_required,
    set_access_cookies,
)
from sqlalchemy import String, create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

JsonResponse: TypeAlias = tuple[Any, int]

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), default="USER", server_default=text("'USER'"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.current_timestamp(), nullable=False
    )


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be set before starting the service")
    return value


def _create_session_factory() -> sessionmaker[Session]:
    engine = create_engine(_required_env("DATABASE_URL"))
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _json_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at.isoformat(),
    }


app = Flask(__name__)
app.config.update(
    JWT_SECRET_KEY=_required_env("JWT_SECRET_KEY"),
    JWT_TOKEN_LOCATION=["cookies"],
    JWT_COOKIE_SECURE=os.getenv("JWT_COOKIE_SECURE", "false").lower() == "true",
    JWT_COOKIE_SAMESITE=os.getenv("JWT_COOKIE_SAMESITE", "Lax"),
    JWT_COOKIE_CSRF_PROTECT=os.getenv("JWT_COOKIE_CSRF_PROTECT", "true").lower()
    == "true",
    SWAGGER={
        "title": "Airport Management Authentication API",
        "uiversion": 3,
        "securityDefinitions": {
            "cookieAuth": {
                "type": "apiKey",
                "in": "cookie",
                "name": "access_token_cookie",
            }
        },
    },
)
session_factory = _create_session_factory()
JWTManager(app)
Swagger(app)

@app.get("/")
@jwt_required()
def home():
    claims = get_jwt()
    return render_template("index.html", logged_in=True)

@app.route("/register", methods=["GET", "POST"])
def register() -> JsonResponse:
    if request.method == "GET":
        return render_template("register.html")

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Request body must be a JSON object"), 400

    required_fields = ("first_name", "last_name", "email", "password")
    if any(
        not isinstance(payload.get(field), str) or not payload[field].strip()
        for field in required_fields
    ):
        return jsonify(error="first_name, last_name, email, and password are required"), 400

    email = payload["email"].strip().lower()
    if "@" not in email or len(payload["password"]) < 8:
        return jsonify(error="A valid email and password of at least 8 characters are required"), 400

    user = User(
        first_name=payload["first_name"].strip(),
        last_name=payload["last_name"].strip(),
        email=email,
        password_hash=bcrypt.hashpw(
            payload["password"].encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8"),
    )

    with session_factory() as session:
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return jsonify(error="A user with that email already exists"), 409

    response = jsonify(user=_json_user(user))
    set_access_cookies(
        response,
        create_access_token(
            identity=str(user.id),
            additional_claims={
                "user_id": user.id,
                "role": user.role,
            },
        ),
    )
    return response, 201

@app.route("/login", methods=["GET", "POST"])
def login() -> JsonResponse:
    if request.method == "GET":
        return render_template("login.html")

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Request body must be a JSON object"), 400

    username = payload.get("username")
    password = payload.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify(error="username and password are required"), 400

    with session_factory() as session:
        user = session.scalar(
            select(User).where(User.email == username.strip().lower())
        )
    if user is None or not bcrypt.checkpw(
        password.encode("utf-8"), user.password_hash.encode("utf-8")
    ):
        return jsonify(error="Invalid username or password"), 401

    response = jsonify(message="Login successful", user=_json_user(user))
    set_access_cookies(
        response,
        create_access_token(
            identity=str(user.id),
            additional_claims={
                "user_id": user.id,
                "role": user.role,
            },
        ),
    )
    return response, 200

@app.post("/logout")
def logout() -> JsonResponse:
    response = redirect(url_for("login"))
    response.delete_cookie("access_token_cookie")
    response.delete_cookie("csrf_access_token")
    return response

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))