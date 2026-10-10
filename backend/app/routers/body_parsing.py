"""Validation for request bodies that a handler parses by hand (JSON or form)."""
from typing import Any, TypeVar

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError

Model = TypeVar("Model", bound=BaseModel)


def parse_body(model: type[Model], data: Any) -> Model:
    """Validate ``data`` like FastAPI validates a declared body: errors answer 422."""
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise RequestValidationError([
            {"type": e["type"], "loc": ("body", *e["loc"]), "msg": e["msg"], "input": e.get("input")}
            for e in exc.errors()
        ])
