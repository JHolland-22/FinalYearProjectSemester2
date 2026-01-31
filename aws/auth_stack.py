from aws_cdk import Stack, CfnOutput, RemovalPolicy
from constructs import Construct
import aws_cdk.aws_cognito as cognito

class AuthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        pool = cognito.UserPool(self, "Pool",
            self_sign_up_enabled=True,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            sign_in_aliases=cognito.SignInAliases(email=True),
            removal_policy=RemovalPolicy.DESTROY
        )

        client = pool.add_client("app-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                admin_user_password=True
            )
        )

        CfnOutput(self, "UserPoolId", value=pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=client.user_pool_client_id)
