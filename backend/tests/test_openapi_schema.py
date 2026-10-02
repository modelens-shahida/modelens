"""
OpenAPI schema quality checks.

These guard the generated documentation only: the schema must build, every
operation must be documented, operation IDs must be unique and every $ref and
tag must resolve.
"""
import json
import warnings

import pytest

from app.main import app

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


@pytest.fixture(scope="module")
def schema():
    app.openapi_schema = None  # force a fresh build
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # FastAPI warns on duplicate operation IDs
        return app.openapi()


def _operations(schema):
    for section in ("paths", "webhooks"):
        for path, item in (schema.get(section) or {}).items():
            for method, operation in item.items():
                if method in HTTP_METHODS:
                    yield f"{section}:{method.upper()} {path}", operation


def _refs(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                yield value
            else:
                yield from _refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _refs(item)


def test_openapi_builds_and_serializes(schema):
    dumped = json.dumps(schema)
    assert json.loads(dumped)["info"]["title"]
    assert schema["paths"]
    assert schema["info"]["version"]
    assert schema["info"]["contact"]["email"]
    assert schema["info"]["license"]["name"]


def test_operation_ids_are_unique(schema):
    seen = {}
    duplicates = []
    for name, operation in _operations(schema):
        op_id = operation.get("operationId")
        assert op_id, f"{name} has no operationId"
        if op_id in seen:
            duplicates.append(f"{op_id}: {seen[op_id]} and {name}")
        seen[op_id] = name
    assert not duplicates, "Duplicate operation IDs:\n" + "\n".join(duplicates)


def test_all_refs_resolve(schema):
    components = schema.get("components", {})
    missing = set()
    for ref in _refs(schema):
        assert ref.startswith("#/components/"), f"Unexpected external $ref {ref}"
        _, _, section, name = ref.split("/", 3)
        if name not in components.get(section, {}):
            missing.add(ref)
    assert not missing, f"Unresolved $refs: {sorted(missing)}"


def test_every_operation_is_documented(schema):
    problems = []
    for name, operation in _operations(schema):
        if not operation.get("summary"):
            problems.append(f"{name}: missing summary")
        if not operation.get("description"):
            problems.append(f"{name}: missing description")
        if not operation.get("tags"):
            problems.append(f"{name}: missing tags")
        responses = operation.get("responses") or {}
        if not responses:
            problems.append(f"{name}: no documented responses")
        success = [r for code, r in responses.items() if code.startswith("2")]
        if success and all(r.get("description") == "Successful Response" for r in success):
            problems.append(f"{name}: missing response_description")
    assert not problems, "\n".join(problems)


def test_every_tag_is_declared(schema):
    declared = {tag["name"] for tag in schema.get("tags", [])}
    used = {tag for _, operation in _operations(schema) for tag in operation.get("tags", [])}
    assert not used - declared, f"Tags used but not declared in openapi_tags: {sorted(used - declared)}"
    assert all(tag.get("description") for tag in schema["tags"])


def test_error_responses_use_shared_schema(schema):
    assert "ErrorResponse" in schema["components"]["schemas"]
    for name, operation in _operations(schema):
        for code in ("400", "401", "403", "404", "429"):
            response = operation.get("responses", {}).get(code)
            if response:
                ref = response["content"]["application/json"]["schema"]["$ref"]
                assert ref.endswith("/ErrorResponse"), f"{name} {code} uses {ref}"


def test_api_key_security_scheme(schema):
    schemes = schema["components"]["securitySchemes"]
    api_key = next(s for s in schemes.values() if s.get("type") == "apiKey")
    assert api_key["in"] == "header"
    assert api_key["name"] == "X-API-Key"
    assert api_key.get("description")
    secured = [op for _, op in _operations(schema) if op.get("security")]
    assert secured, "No operation declares a security requirement"


def test_webhook_signature_headers_documented(schema):
    delivery = schema["webhooks"]["webhookDelivery"]["post"]
    headers = {p["name"]: p for p in delivery["parameters"] if p["in"] == "header"}
    for header in ("X-Modelens-Signature-256", "X-Modelens-Timestamp"):
        assert header in headers
        assert headers[header]["required"] is True
        assert headers[header].get("description")
    assert headers["X-Modelens-Signature-256"]["schema"]["examples"][0].startswith("sha256=")


def test_pagination_params_documented(schema):
    found = 0
    for name, operation in _operations(schema):
        for param in operation.get("parameters", []):
            if param["in"] == "query" and param["name"] in ("limit", "offset", "page"):
                found += 1
                assert param.get("description"), f"{name}: `{param['name']}` has no description"
                assert "default" in param["schema"], f"{name}: `{param['name']}` has no default"
                assert param["schema"].get("examples"), f"{name}: `{param['name']}` has no example"
    assert found
