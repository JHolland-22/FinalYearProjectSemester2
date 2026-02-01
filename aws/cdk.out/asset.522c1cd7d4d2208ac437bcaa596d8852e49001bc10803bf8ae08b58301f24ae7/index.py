import boto3

cognito = boto3.client("cognito-idp")


def handler(event, context):
    email = event["request"]["userAttributes"].get("email", "")

    group_name = "Student" if email and email[0].isdigit() else "Educator"

    try:
        cognito.admin_add_user_to_group(
            UserPoolId=event["userPoolId"],
            Username=event["userName"],
            GroupName=group_name
        )
    except Exception as e:
        print(f"Error adding {email} to group {group_name}: {str(e)}")

    return event
