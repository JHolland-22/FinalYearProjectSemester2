from flask import render_template, url_for, flash, redirect, request, session
from flask_login import login_user, current_user, logout_user, login_required
from .aws_utils import list_user_amis_from_session, share_user_ami_from_session
from botocore.exceptions import ClientError
import boto3
import os
import re
from . import app, get_user_group
##from .models import User, VM
from .forms import (
    RegistrationForm,
    LoginForm,
    UpdateAccountForm,
    AmiShareForm,
    ConfirmForm
)

AWS_REGION = os.environ.get("AWS_REGION")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")

cognito_client = boto3.client("cognito-idp", region_name=AWS_REGION)
ec2 = boto3.client("ec2", region_name="eu-west-1")


def get_instance_id_by_name(name):
    reservations = ec2.describe_instances(
        Filters=[{"Name": "tag:Name", "Values": [name]}]
    )["Reservations"]
    if reservations:
        return reservations[0]["Instances"][0]["InstanceId"]
    return None


@app.route("/")
@app.route("/home")
def home():
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html", title="About")


@app.route("/start_kali")
def start_kali():
    instance_id = get_instance_id_by_name("KaliVM")
    ec2.start_instances(InstanceIds=[instance_id])
    return redirect(url_for("home"))


@app.route("/stop_kali")
def stop_kali():
    instance_id = get_instance_id_by_name("KaliVM")
    ec2.stop_instances(InstanceIds=[instance_id])
    return redirect(url_for("home"))


@app.route("/start_ubuntu")
def start_ubuntu():
    instance_id = get_instance_id_by_name("UbuntuVM")
    ec2.start_instances(InstanceIds=[instance_id])
    return redirect(url_for("home"))


@app.route("/stop_ubuntu")
def stop_ubuntu():
    instance_id = get_instance_id_by_name("UbuntuVM")
    ec2.stop_instances(InstanceIds=[instance_id])
    return redirect(url_for("home"))




@app.route("/register", methods=["GET", "POST"])
def register():
    # Redirect logged-in users to home
    if session.get("email"):
        return redirect(url_for("home"))

    form = RegistrationForm()

    if form.validate_on_submit():
        # Determine role from email prefix
        identifier, _, _ = form.email.data.partition('@')
        role = "Student" if re.fullmatch(r'\d+', identifier) else "Educator"

        try:
            cognito_client.sign_up(
                ClientId=COGNITO_CLIENT_ID,
                Username=form.email.data,
                Password=form.password.data,
                UserAttributes=[
                    {"Name": "email", "Value": form.email.data},
                    {"Name": "custom:role", "Value": role},
                    {"Name": "custom:class_group", "Value": form.class_group.data},
                ],
            )
        except cognito_client.exceptions.UsernameExistsException:
            flash("User already exists. Please confirm or log in.", "danger")
            return render_template("register.html", form=form)
        except Exception as e:
            flash(f"Registration failed: {e}", "danger")
            return render_template("register.html", form=form)

        flash("A confirmation code has been sent to your email.", "info")
        return redirect(url_for("confirm", email=form.email.data))

    return render_template("register.html", form=form)







@app.route("/confirm", methods=["GET", "POST"])
def confirm():
    form = ConfirmForm()
    if request.method == "GET":
        form.email.data = request.args.get("email")

    if form.validate_on_submit():
        if form.resend.data:
            try:
                cognito_client.resend_confirmation_code(
                    ClientId=COGNITO_CLIENT_ID,
                    Username=form.email.data,
                )
                flash("New confirmation code sent.", "info")
            except Exception as e:
                flash(f"Could not resend code: {e}", "danger")
            return render_template("confirm.html", form=form)

        try:
            cognito_client.confirm_sign_up(
                ClientId=COGNITO_CLIENT_ID,
                Username=form.email.data,
                ConfirmationCode=form.code.data,
            )
        except Exception as e:
            flash(f"Confirmation failed: {e}", "danger")
            return render_template("confirm.html", form=form)

        return redirect(url_for("choose_role", email=form.email.data))

    return render_template("confirm.html", form=form)






@app.route("/choose_role", methods=["GET"])
def choose_role():
    return render_template("choose_role.html")





@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("email"):
        return redirect(url_for("home"))

    form = LoginForm()

    if form.validate_on_submit():
        try:
            cognito_client.initiate_auth(
                ClientId=COGNITO_CLIENT_ID,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": form.email.data,
                    "PASSWORD": form.password.data,
                },
            )

            session.clear()
            session["email"] = form.email.data
            session["role"] = get_user_group(form.email.data)

            role_arn = form.aws_role_arn.data
            assume_args = {
                "RoleArn": role_arn,
                "RoleSessionName": "FlaskAppSession"
            }

            if form.aws_external_id.data:
                assume_args["ExternalId"] = form.aws_external_id.data

            sts_client = boto3.client("sts")
            sts_response = sts_client.assume_role(**assume_args)

            creds = sts_response["Credentials"]
            session["aws_access_key_id"] = creds["AccessKeyId"]
            session["aws_secret_access_key"] = creds["SecretAccessKey"]
            session["aws_session_token"] = creds["SessionToken"]

            flash("Logged in successfully with AWS credentials.", "success")
            return redirect(url_for("home"))

        except cognito_client.exceptions.UserNotConfirmedException:
            flash("Account not confirmed", "warning")
        except cognito_client.exceptions.NotAuthorizedException:
            flash("Invalid email or password", "danger")
        except ClientError as e:
            flash(e.response["Error"]["Message"], "danger")

    return render_template("login.html", form=form)




@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("choose_role"))






@app.route("/account", methods=["GET", "POST"])
def account():
    if "email" not in session:
        return redirect(url_for("login"))

    form = UpdateAccountForm()

    if form.validate_on_submit():
        # Cognito handles users, so we just update session if needed
        session["role"] = form.username.data  # Example: update role display
        session["email"] = form.email.data
        flash("Account info updated (session only, Cognito manages backend).", "success")
        return redirect(url_for("account"))

    form.username.data = session.get("role", "")
    form.email.data = session.get("email", "")

    return render_template("account.html", form=form)



@app.route("/ami_share", methods=["GET", "POST"])
def share_ami():
    aws_access_key_id = session.get("aws_access_key_id")
    aws_secret_access_key = session.get("aws_secret_access_key")
    aws_session_token = session.get("aws_session_token")

    if not aws_access_key_id or not aws_secret_access_key or not aws_session_token:
        flash("You must log in with AWS credentials first.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        ami_id = request.form.get("ami_select")
        account_ids = request.form.get("aws_accounts").replace(" ", "").split(",")
        try:
            share_user_ami_from_session(
                aws_access_key_id,
                aws_secret_access_key,
                aws_session_token,
                ami_id,
                account_ids,
                region="eu-west-1"
            )
            flash(f"AMI {ami_id} shared successfully!", "success")
            return redirect(url_for("ami"))
        except ClientError as e:
            flash(f"Error: {e.response['Error']['Message']}", "danger")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            return redirect(url_for("share_ami"))

    amis = list_user_amis_from_session(
        aws_access_key_id,
        aws_secret_access_key,
        aws_session_token
    )
    amis_list = [{"ami_id": img["ImageId"], "name": img.get("Name", "Unnamed AMI")} for img in amis]

    return render_template("ami_share.html", amis=amis_list)




@app.route("/ami", methods=["GET"])
def ami():
    ec2 = boto3.client('ec2', region_name='us-east-1')
    response = ec2.describe_images(Owners=['self'])

    amis = [
        {'ami_id': img['ImageId'], 'name': img.get('Name', 'Unnamed AMI')}
        for img in response['Images']
    ]

    return render_template("ami.html", amis=amis)




@app.route("/labs", methods=["GET"])
def labs():
    fake_categories = ["Networking", "Databases", "Security", "Machine Learning"]
    return render_template("labs.html", categories=fake_categories)






@app.route("/labsupload", methods=["GET", "POST"])
def lab_upload():
    fake_categories = ["Networking", "Databases", "Security", "Machine Learning"]
    return render_template("labs_upload.html", categories=fake_categories)







@app.route("/login-choice")
def login_choice():
    return render_template("choose_role.html")