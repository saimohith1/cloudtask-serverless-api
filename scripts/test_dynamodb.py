import sys
from pathlib import Path

# Add the project root to Python's module search path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone
from uuid import uuid4

from hello_world import repository


user_id = "local-user"
task_id = str(uuid4())
timestamp = datetime.now(timezone.utc).isoformat()

task = {
    "user_id": user_id,
    "task_id": task_id,
    "title": "Test real DynamoDB",
    "description": "Testing CloudTask database",
    "status": "PENDING",
    "created_at": timestamp,
    "updated_at": timestamp
}

print("Starting DynamoDB integration tests...\n")

# CREATE
repository.create_task(task)
print("CREATE: SUCCESS")

# READ ONE
created = repository.get_task(user_id, task_id)
assert created is not None
assert created["title"] == "Test real DynamoDB"
print("READ ONE: SUCCESS")

# READ ALL
tasks = repository.list_tasks(user_id)
assert any(t["task_id"] == task_id for t in tasks)
print("READ ALL: SUCCESS")

# UPDATE
updated = repository.update_task(
    user_id,
    task_id,
    {
        "title": "Updated DynamoDB task",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
)

assert updated["title"] == "Updated DynamoDB task"
print("UPDATE: SUCCESS")

# DELETE
deleted = repository.delete_task(user_id, task_id)
assert deleted is not None
print("DELETE: SUCCESS")

# VERIFY DELETION
assert repository.get_task(user_id, task_id) is None
print("DELETE VERIFICATION: SUCCESS")

print("\nAll DynamoDB operations passed!")
