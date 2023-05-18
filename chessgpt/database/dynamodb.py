import os
import boto3


def get_dynamodb_client():
    # setup the dynamodb client
    if os.environ.get("IS_OFFLINE") == "True":
        print("Running in offline mode")
        session = boto3.Session(
            aws_access_key_id="DUMMY", aws_secret_access_key="DUMMY"
        )
        return session.resource(
            "dynamodb", region_name="localhost", endpoint_url="http://localhost:8000"
        ).meta.client
    else:
        session = boto3.Session()
        return session.resource("dynamodb").meta.client
