from aws_cdk import Stack, CfnOutput, RemovalPolicy
from constructs import Construct
import aws_cdk.aws_cognito as cognito
import aws_cdk.aws_lambda as _lambda
import aws_cdk.aws_iam as iam

class AuthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        pool = cognito.UserPool(
            self,
            "Pool",
            self_sign_up_enabled=True,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            sign_in_aliases=cognito.SignInAliases(email=True),
            custom_attributes={
                "role": cognito.StringAttribute(min_len=3, max_len=20)
            },
            removal_policy=RemovalPolicy.DESTROY
        )

        client = pool.add_client(
            "app-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                admin_user_password=True
            ),
            generate_secret=False
        )

        cognito.CfnUserPoolGroup(
            self,
            "StudentGroup",
            group_name="Student",
            user_pool_id=pool.user_pool_id
        )

        cognito.CfnUserPoolGroup(
            self,
            "EducatorGroup",
            group_name="Educator",
            user_pool_id=pool.user_pool_id
        )

        post_confirmation_lambda = _lambda.Function(
            self,
            "PostConfirmationLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.Code.from_asset("lambda")
        )

        post_confirmation_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cognito-idp:AdminAddUserToGroup"],
                resources=["*"]
            )
        )

        pool.add_trigger(
            cognito.UserPoolOperation.POST_CONFIRMATION,
            post_confirmation_lambda
        )

        CfnOutput(self, "UserPoolId", value=pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=client.user_pool_client_id)
