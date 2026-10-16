from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar, cast

from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException

F = TypeVar("F", bound=Callable[..., Any])


def jwt_filter(function: F) -> F:
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            verify_jwt_in_request()
        except JWTExtendedException:
            return jsonify(error="Missing or invalid authentication token"), 401
        return function(*args, **kwargs)

    return cast(F, wrapped)