# Airport Management Authentication API

This service provides registration, login, logout, and JWT cookie authentication for Flask APIs. All APIs should use the same external database system; containers should not create a separate database for each API.

## Shared external database

The service uses SQLAlchemy and connects through the `DATABASE_URL` environment variable. For PostgreSQL, use a URL such as:

```text
postgresql+psycopg://username:password@database-host:5432/airport_management
```

Set the same database URL for this service and any other API that needs to use the shared database:

```bash
export DATABASE_URL="postgresql+psycopg://username:password@database-host:5432/airport_management"
```

The database must be reachable from the containers. Do not use `localhost` in `DATABASE_URL` when the database is running in another container or on another machine; use the database service name or external host instead.

The authentication service creates its `users` table when it starts. For production, use a migration tool such as Alembic when changing an existing shared schema. Other APIs should add their own tables to the same database rather than creating another database.

## Authenticate another Flask API

The authentication service stores the JWT in the `access_token_cookie` cookie. The token contains:

```json
{
  "sub": "1",
  "user_id": 1,
  "role": "USER"
}
```

Your API must use the same `JWT_SECRET_KEY` as the authentication service.

### 1. Copy the JWT filter

Copy [jwt_filter.py](./jwt_filter.py) into your Flask API project.

Install the required packages:

```text
Flask>=3.1,<4
Flask-JWT-Extended>=4.7,<5
```

Add them to your API's `requirements.txt`:

```text
Flask>=3.1,<4
Flask-JWT-Extended>=4.7,<5
```

### 2. Configure your Flask API

```python
import os

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager, get_jwt, get_jwt_identity

from jwt_filter import jwt_filter

app = Flask(__name__)
app.config.update(
    JWT_SECRET_KEY=os.environ["JWT_SECRET_KEY"],
    JWT_TOKEN_LOCATION=["cookies"],
    JWT_COOKIE_SECURE=os.getenv("JWT_COOKIE_SECURE", "false").lower() == "true",
    JWT_COOKIE_SAMESITE=os.getenv("JWT_COOKIE_SAMESITE", "Lax"),
    JWT_COOKIE_CSRF_PROTECT=os.getenv("JWT_COOKIE_CSRF_PROTECT", "true").lower()
    == "true",
)
JWTManager(app)


@app.get("/protected")
@jwt_filter
def protected():
    claims = get_jwt()
    return jsonify(
        message="Authenticated",
        user_id=get_jwt_identity(),
        role=claims["role"],
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")))
```

Apply `@jwt_filter` to every endpoint that requires authentication.

Use `get_jwt_identity()` to read the token subject and `get_jwt()` to read the additional claims:

```python
user_id = get_jwt_identity()
claims = get_jwt()
role = claims["role"]
```

### 3. Environment variables

Your API needs these values:

```bash
export JWT_SECRET_KEY="use-the-same-long-random-secret-as-the-auth-service"
export PORT=5001
export JWT_COOKIE_SECURE=false
export JWT_COOKIE_SAMESITE=Lax
export JWT_COOKIE_CSRF_PROTECT=true
```

Use `JWT_COOKIE_SECURE=true` when running behind HTTPS. Both services must use the same `JWT_SECRET_KEY` and compatible cookie settings.

When CSRF protection is enabled, state-changing requests to protected endpoints must also send the `csrf_access_token` cookie value in the `X-CSRF-TOKEN` header.

### 4. Dockerfile for your Flask API

Create a separate `Dockerfile` in your API project:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py jwt_filter.py ./
COPY templates ./templates
COPY static ./static

ENV PORT=5001
EXPOSE 5001

CMD ["python", "app.py"]
```

If your API has a browser interface, keep its Jinja files in a `templates/` directory and its CSS, JavaScript, and image files in a `static/` directory. The `COPY` lines above make those directories available to Flask inside the container. Add any other application files or directories your API imports or serves to the Dockerfile as well.

Build and run your API:

```bash
docker build -t my-flask-api .

docker run --rm \
  --name my-flask-api \
  -p 5001:5001 \
  -e PORT=5001 \
  -e JWT_SECRET_KEY="$JWT_SECRET_KEY" \
  -e DATABASE_URL="$DATABASE_URL" \
  -e JWT_COOKIE_SECURE=false \
  -e JWT_COOKIE_SAMESITE=Lax \
  -e JWT_COOKIE_CSRF_PROTECT=true \
  my-flask-api
```

## Run the authentication service

Build the image:

```bash
docker build -t airport-auth .
```

Run it on host port `5002`:

```bash
docker run --rm \
  --name airport-auth \
  -p 5002:5000 \
  -e JWT_SECRET_KEY="$JWT_SECRET_KEY" \
  -e DATABASE_URL="$DATABASE_URL" \
  -e JWT_COOKIE_SECURE=false \
  -e JWT_COOKIE_SAMESITE=Lax \
  -e JWT_COOKIE_CSRF_PROTECT=true \
  airport-auth
```

The authentication service is available at `http://localhost:5002`.

Register or log in first:

```text
POST http://localhost:5002/register
POST http://localhost:5002/login
```

Then call your protected API. When using Postman, keep cookie storage enabled so the `access_token_cookie` is sent to the other API.
