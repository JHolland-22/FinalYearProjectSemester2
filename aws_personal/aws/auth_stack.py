from aws_cdk import Stack, CfnOutput, RemovalPolicy
from constructs import Construct
import aws_cdk.aws_cognito as cognito
import aws_cdk.aws_lambda as _lambda
import aws_cdk.aws_iam as iam

class AuthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Cognito User Pool for managing student and educator authentication
        # Users can self-register and are verified via email confirmation code
        pool = cognito.UserPool(
            self,
            "Pool",
            self_sign_up_enabled=True,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            sign_in_aliases=cognito.SignInAliases(email=True),
            # Custom attributes store user role (Student/Educator) and class group
            # These are set during registration and used to control access to templates and labs
            custom_attributes={
                "role": cognito.StringAttribute(min_len=3, max_len=20),
                "class_group": cognito.StringAttribute(min_len=3, max_len=50)
            },
            removal_policy=RemovalPolicy.DESTROY
        )

        # App client used by the Flask web app to authenticate users via the Cognito API
        # No client secret is generated as the Flask app uses the USER_PASSWORD_AUTH flow
        client = pool.add_client(
            "app-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                admin_user_password=True
            ),
            generate_secret=False
        )

        # Create the Student group in Cognito for role-based access control
        cognito.CfnUserPoolGroup(
            self,
            "StudentGroup",
            group_name="Student",
            user_pool_id=pool.user_pool_id
        )

        # Create the Educator group in Cognito for role-based access control
        cognito.CfnUserPoolGroup(
            self,
            "EducatorGroup",
            group_name="Educator",
            user_pool_id=pool.user_pool_id
        )

        # Lambda function triggered after a user confirms their email
        # Automatically assigns the user to the correct Cognito group (Student or Educator)
        # based on the custom:role attribute set during registration
        post_confirmation_lambda = _lambda.Function(
            self,
            "PostConfirmationLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_asset("lambda")
        )

        # Grant the Lambda function permission to add users to Cognito groups
        post_confirmation_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cognito-idp:AdminAddUserToGroup"],
                resources=["*"]
            )
        )

        # Attach the Lambda function as a post-confirmation trigger on the User Pool
        # This runs automatically after a user successfully verifies their email
        pool.add_trigger(
            cognito.UserPoolOperation.POST_CONFIRMATION,
            post_confirmation_lambda
        )

        # Output the User Pool ID and Client ID so they can be used as environment variables for the Flask app
        CfnOutput(self, "UserPoolId", value=pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=client.user_pool_client_id)