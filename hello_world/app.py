import json
import logging
import uuid
from datetime import datetime, timezone

try:
    from . import repository
except ImportError:
    import repository


logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALLOWED_STATUSES = {"PENDING", "IN_PROGRESS", "COMPLETED"}
MAX_TITLE_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 1000


def response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload)
    }


def get_user_id(event):
    """Extract the authenticated Cognito user ID from API Gateway."""

    authorizer = (
        event.get("requestContext", {})
        .get("authorizer", {})
    )

    # API Gateway REST API Cognito authorizer
    claims = authorizer.get("claims", {})

    # Also support API Gateway HTTP API JWT authorizer
    if not claims:
        claims = authorizer.get("jwt", {}).get("claims", {})

    return claims.get("sub")


def get_task_id(event):
    path_parameters = event.get("pathParameters") or {}

    if path_parameters.get("task_id"):
        return path_parameters["task_id"]

    path = event.get("path", "")
    parts = path.strip("/").split("/")

    if len(parts) == 2 and parts[0] == "tasks":
        return parts[1]

    return None


def parse_body(event):
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return None, response(400, {"error": "Invalid JSON"})

    if not isinstance(body, dict):
        return None, response(
            400,
            {"error": "Request body must be a JSON object"}
        )

    return body, None


def validate_task_fields(data, is_update=False):
    allowed_fields = {"title", "description", "status"}

    unknown_fields = set(data.keys()) - allowed_fields

    if unknown_fields:
        return None, "Unsupported task fields"

    if not is_update or "title" in data:
        title = data.get("title")

        if not isinstance(title, str) or not title.strip():
            return None, "Title is required"

        title = title.strip()

        if len(title) > MAX_TITLE_LENGTH:
            return None, "Title exceeds 120 characters"

        data["title"] = title

    if "description" in data:
        description = data["description"]

        if not isinstance(description, str):
            return None, "Description must be a string"

        if len(description) > MAX_DESCRIPTION_LENGTH:
            return None, "Description exceeds 1000 characters"

        data["description"] = description.strip()

    if "status" in data:
        status = data["status"]

        if not isinstance(status, str):
            return None, "Status must be a string"

        status = status.upper()

        if status not in ALLOWED_STATUSES:
            return None, "Invalid task status"

        data["status"] = status

    if is_update and not data:
        return None, "At least one field must be provided"

    return data, None


def lambda_handler(event, context):
    method = str(event.get("httpMethod", "GET")).upper()
    path = event.get("path", "/")

    logger.info(json.dumps({
        "event": "request_received",
        "method": method,
        "path": path
    }))

    # Public health endpoint
    if path == "/health" and method == "GET":
        return response(200, {
            "status": "healthy",
            "service": "CloudTask API"
        })

    # Public informational endpoint
    if path == "/hello" and method == "GET":
        return response(200, {
            "message": "CloudTask API is running"
        })

    # All task endpoints require an authenticated identity
    user_id = get_user_id(event)

    if not user_id:
        return response(401, {
            "error": "Unauthorized"
        })

    # CREATE TASK
    if path == "/tasks" and method == "POST":
        body, error_response = parse_body(event)

        if error_response:
            return error_response

        validated, error = validate_task_fields(body)

        if error:
            return response(400, {"error": error})

        timestamp = datetime.now(timezone.utc).isoformat()

        task = {
            "user_id": user_id,
            "task_id": str(uuid.uuid4()),
            "title": validated["title"],
            "description": validated.get("description", ""),
            "status": validated.get("status", "PENDING"),
            "created_at": timestamp,
            "updated_at": timestamp
        }

        try:
            repository.create_task(task)

            logger.info(json.dumps({
                "event": "task_created",
                "task_id": task["task_id"]
            }))

            return response(201, {
                "message": "Task created successfully",
                "task": task
            })

        except Exception:
            logger.exception("Failed to create task")
            return response(500, {
                "error": "Unable to create task"
            })

    # LIST TASKS
    if path == "/tasks" and method == "GET":
        try:
            tasks = repository.list_tasks(user_id)

            return response(200, {
                "count": len(tasks),
                "tasks": tasks
            })

        except Exception:
            logger.exception("Failed to list tasks")
            return response(500, {
                "error": "Unable to retrieve tasks"
            })

    task_id = get_task_id(event)

    if task_id:

        # GET TASK
        if method == "GET":
            try:
                task = repository.get_task(user_id, task_id)

                if not task:
                    return response(404, {
                        "error": "Task not found"
                    })

                return response(200, {"task": task})

            except Exception:
                logger.exception("Failed to retrieve task")
                return response(500, {
                    "error": "Unable to retrieve task"
                })

        # UPDATE TASK
        if method == "PUT":
            body, error_response = parse_body(event)

            if error_response:
                return error_response

            validated, error = validate_task_fields(
                body,
                is_update=True
            )

            if error:
                return response(400, {"error": error})

            validated["updated_at"] = (
                datetime.now(timezone.utc).isoformat()
            )

            try:
                updated = repository.update_task(
                    user_id,
                    task_id,
                    validated
                )

                if not updated:
                    return response(404, {
                        "error": "Task not found"
                    })

                return response(200, {
                    "message": "Task updated successfully",
                    "task": updated
                })

            except Exception:
                logger.exception("Failed to update task")
                return response(500, {
                    "error": "Unable to update task"
                })

        # DELETE TASK
        if method == "DELETE":
            try:
                deleted = repository.delete_task(
                    user_id,
                    task_id
                )

                if not deleted:
                    return response(404, {
                        "error": "Task not found"
                    })

                return response(200, {
                    "message": "Task deleted successfully",
                    "task": deleted
                })

            except Exception:
                logger.exception("Failed to delete task")
                return response(500, {
                    "error": "Unable to delete task"
                })

    return response(404, {"error": "Route not found"})
