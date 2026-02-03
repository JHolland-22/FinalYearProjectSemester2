from flask import render_template, url_for, flash, redirect, request, session
from flask_login import login_user, current_user, logout_user, login_required
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


@app.route("/choose_role", methods=["GET", "POST"])
def choose_role():
    email = request.args.get("email")
    if not email:
        flash("Email missing", "danger")
        return redirect(url_for("login"))

    identifier, _, _ = email.partition('@')
    allowed_role = "Student" if identifier.isdigit() else "Educator"

    if request.method == "POST":
        selected_role = request.form.get("role")
        if selected_role != allowed_role:
            flash("You cannot select this role for your email.", "danger")
            return redirect(url_for("choose_role", email=email))
        flash(f"Role {selected_role} confirmed! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("choose_role.html", allowed_role=allowed_role, email=email)


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
            session["email"] = form.email.data
            session["role"] = get_user_group(form.email.data)
            flash("Logged in successfully!", "success")
            return redirect(url_for("home"))
        except cognito_client.exceptions.UserNotConfirmedException:
            flash("Account not confirmed", "warning")
        except cognito_client.exceptions.NotAuthorizedException:
            flash("Invalid email or password", "danger")

    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("home"))


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


from flask import render_template

@app.route("/amishare", methods=["GET", "POST"])
def amishare():
    fake_amis = [
        {"ami_id": "ami-0abcd1234efgh5678", "name": "Ubuntu 22.04"},
        {"ami_id": "ami-1abcd1234efgh5678", "name": "Windows Server 2019"},
        {"ami_id": "ami-2abcd1234efgh5678", "name": "Amazon Linux 2"}
    ]
    return render_template("ami_share.html", amis=fake_amis)

@app.route("/ami", methods=["GET"])
def ami():
    fake_shared_amis = [
        {"ami_id": "ami-0abcd1234efgh5678", "name": "Ubuntu 22.04"},
        {"ami_id": "ami-1abcd1234efgh5678", "name": "Windows Server 2019"}
    ]
    return render_template("ami.html", amis=fake_shared_amis)

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
