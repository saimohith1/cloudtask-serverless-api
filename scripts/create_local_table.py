import boto3
import os

dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url=os.environ["DYNAMODB_ENDPOINT_URL"],
    region_name=os.environ["AWS_DEFAULT_REGION"]
)

table_name = os.environ["TASKS_TABLE"]

existing_tables = list(
    dynamodb.meta.client.list_tables()["TableNames"]
)

if table_name in existing_tables:
    print(f"Table {table_name} already exists.")
else:
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "task_id", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "task_id", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST"
    )

    table.wait_until_exists()
    print(f"Created table: {table_name}")

print("Local DynamoDB setup complete.")
