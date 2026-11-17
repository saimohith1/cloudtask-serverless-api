import os
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError


def get_table():
    table_name = os.environ.get("TASKS_TABLE")

    if not table_name:
        raise RuntimeError("TASKS_TABLE environment variable is not configured")

    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL") or None

    dynamodb = boto3.resource(
        "dynamodb",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"),
        endpoint_url=endpoint_url
    )

    return dynamodb.Table(table_name)


def create_task(task):
    table = get_table()
    table.put_item(Item=task)
    return task


def list_tasks(user_id):
    table = get_table()
    items = []

    query_params = {
        "KeyConditionExpression": Key("user_id").eq(user_id)
    }

    while True:
        result = table.query(**query_params)
        items.extend(result.get("Items", []))

        last_key = result.get("LastEvaluatedKey")

        if not last_key:
            break

        query_params["ExclusiveStartKey"] = last_key

    return items


def get_task(user_id, task_id):
    table = get_table()

    result = table.get_item(
        Key={
            "user_id": user_id,
            "task_id": task_id
        }
    )

    return result.get("Item")


def update_task(user_id, task_id, updates):
    table = get_table()

    expression_names = {}
    expression_values = {}
    update_parts = []

    for field, value in updates.items():
        if field == "updated_at":
            continue

        expression_names[f"#{field}"] = field
        expression_values[f":{field}"] = value
        update_parts.append(f"#{field} = :{field}")

    expression_names["#updated_at"] = "updated_at"
    expression_values[":updated_at"] = updates["updated_at"]
    update_parts.append("#updated_at = :updated_at")

    try:
        result = table.update_item(
            Key={
                "user_id": user_id,
                "task_id": task_id
            },
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values,
            ConditionExpression=Attr("task_id").exists(),
            ReturnValues="ALL_NEW"
        )

        return result.get("Attributes")

    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return None
        raise


def delete_task(user_id, task_id):
    table = get_table()

    try:
        result = table.delete_item(
            Key={
                "user_id": user_id,
                "task_id": task_id
            },
            ConditionExpression=Attr("task_id").exists(),
            ReturnValues="ALL_OLD"
        )

        return result.get("Attributes")

    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return None
        raise
