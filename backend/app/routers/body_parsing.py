"""Validation for request bodies that a handler parses by hand (JSON or form)."""
from typing import Any, Optional, Tuple, TypeVar

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.datastructures import FormData
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


FORM_CONTENT_TYPES = ("multipart/form-data", "application/x-www-form-urlencoded")


async def read_form_or_json(request: Request) -> Tuple[Optional[FormData], Any]:
    """(form, None) for a form post, multipart or urlencoded (a form without files is sent
    urlencoded), else (None, the JSON body). A body that is neither answers 422."""
    if any(t in request.headers.get("content-type", "") for t in FORM_CONTENT_TYPES):
        return await request.form(), None
    try:
        return None, await request.json()
    except ValueError:  # empty or not JSON
        raise RequestValidationError([{"type": "json_invalid", "loc": ("body",),
                                       "msg": "The body must be JSON or form data.", "input": None}])
