import boto3

cognito = boto3.client("cognito-idp")

def handler(event, context):
    role = event["request"]["userAttributes"].get("custom:role")

    if role == "Student":
        group_name = "Student"
    elif role == "Educator":
        group_name = "Educator"
    else:
        raise Exception("Invalid role")

    cognito.admin_add_user_to_group(
        UserPoolId=event["userPoolId"],
        Username=event["userName"],
        GroupName=group_name
    )

    return event
