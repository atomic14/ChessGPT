import boto3
from functools import wraps
from flask import jsonify, request, current_app as app
from cachetools import cached, TTLCache
import os

cache = TTLCache(maxsize=10, ttl=86400)


@cached(cache)
def get_secret(secret_name, region_name):
    session = boto3.session.Session()
    client = session.client(
        service_name="secretsmanager",
        region_name=region_name,
    )

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except Exception as e:
        print("Error retrieving secret. Exception: ", e)
        return None

    return get_secret_value_response["SecretString"]


def check_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        secret_name = os.environ.get("OPENAI_CHESS_SECRET")
        if secret_name:
            auth_header = request.headers.get("Authorization")
            secret = get_secret(os.environ.get("OPENAI_CHESS_SECRET"), "us-east-1")
            expected_value = "Bearer " + secret
            if not auth_header or auth_header != expected_value:
                return jsonify({"message": "Authorization required."}), 401
            else:
                app.logger.info("Authorization successful.")
        else:
            app.logger.info("No authentication required.")
        return f(*args, **kwargs)

    return decorated_function
