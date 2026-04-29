import boto3

# Cognito client used to manage user group assignments
cognito = boto3.client("cognito-idp")

def handler(event, context):
    # This Lambda is triggered by Cognito after a user confirms their email
    # It reads the custom:role attribute set during registration and assigns
    # the user to the matching Cognito group (Student or Educator)

    role = event["request"]["userAttributes"].get("custom:role")

    if role == "Student":
        group_name = "Student"
    elif role == "Educator":
        group_name = "Educator"
    else:
        raise Exception("Invalid role")

    # Add the confirmed user to the appropriate Cognito group
    # This enables role-based access control in the Flask web app
    cognito.admin_add_user_to_group(
        UserPoolId=event["userPoolId"],
        Username=event["userName"],
        GroupName=group_name
    )

    # Return the event object back to Cognito to complete the post-confirmation flow
    return event