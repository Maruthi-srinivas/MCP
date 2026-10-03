"""Keep a resource JSON document inside a character budget."""

import json


def bound_document(payload: dict, limit: int) -> dict:
    """Drop items from the end of lists until the JSON fits. Sets truncated when it cuts."""
    body = dict(payload)
    list_keys = [key for key, value in body.items() if isinstance(value, list)]
    while len(json.dumps(body, sort_keys=True)) > limit:
        shrunk = False
        for key in list_keys:
            if body[key]:
                body[key] = body[key][:-1]
                body["truncated"] = True
                shrunk = True
                break
        if shrunk:
            continue
        content = body.get("content")
        if isinstance(content, str) and content:
            body["content"] = content[: max(0, len(content) // 2)]
            body["truncated"] = True
            if not body["content"]:
                return body
            continue
        body["truncated"] = True
        return body
    return body


def dump_resource(payload: dict, limit: int) -> str:
    """Serialize a bounded document. Key order is stable."""
    return json.dumps(bound_document(payload, limit), sort_keys=True)


def error_document(code: str, message: str, retryable: bool = False) -> str:
    return json.dumps(
        {"error": {"code": code, "message": message, "retryable": retryable}},
        sort_keys=True,
    )
