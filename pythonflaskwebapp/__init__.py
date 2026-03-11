from flask import Flask
import os
import boto3
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')

# Cognito environment variables
COGNITO_REGION = os.getenv("AWS_REGION")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")

cognito_client = boto3.client(
    "cognito-idp",
    region_name=COGNITO_REGION
)

# Function to get user group
def get_user_group(username):
    try:
        response = cognito_client.admin_list_groups_for_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=username
        )
        groups = [g["GroupName"] for g in response.get("Groups", [])]
        if "Educator" in groups:
            return "Educator"
        if "Student" in groups:
            return "Student"
        return None
    except Exception:
        return None

from . import routes

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=True)
