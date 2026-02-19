from flask import render_template, url_for, flash, redirect, request, session
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.utils import secure_filename

from .aws_utils import list_user_amis_from_session, share_user_ami_from_session, get_s3_client
from botocore.exceptions import ClientError
import boto3
import os
import re
import json
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
LABS_BUCKET = os.environ.get('LABS_BUCKET_NAME')
TEMPLATES_BUCKET = os.environ.get('TEMPLATES_BUCKET_NAME')
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



@app.route("/educator_login", methods=["GET", "POST"])
def educator_login():
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
            role = get_user_group(form.email.data)
            session["role"] = role

            # EDUCATOR: Use Role ARN to assume role
            if form.aws_role_arn.data:
                try:
                    sts_client = boto3.client("sts")
                    sts_response = sts_client.assume_role(
                        RoleArn=form.aws_role_arn.data,
                        RoleSessionName="FlaskAppSession"
                    )

                    creds = sts_response["Credentials"]
                    session["aws_access_key_id"] = creds["AccessKeyId"]
                    session["aws_secret_access_key"] = creds["SecretAccessKey"]
                    session["aws_session_token"] = creds["SessionToken"]

                    flash("Logged in successfully with AWS credentials.", "success")
                except ClientError as e:
                    flash(f"AWS Role Error: {e.response['Error']['Message']}", "danger")
                    return render_template("educator_login.html", form=form)
            else:
                flash("Please enter your AWS Role ARN.", "danger")
                return render_template("educator_login.html", form=form)

            return redirect(url_for("home"))

        except cognito_client.exceptions.UserNotConfirmedException:
            flash("Account not confirmed", "warning")
        except cognito_client.exceptions.NotAuthorizedException:
            flash("Invalid email or password", "danger")
        except ClientError as e:
            flash(e.response["Error"]["Message"], "danger")

    return render_template("educator_login.html", form=form)



@app.route("/student_login", methods=["GET", "POST"])
def student_login():
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
            role = get_user_group(form.email.data)
            session["role"] = role

            # STUDENT: Use direct AWS Academy credentials
            if form.aws_access_key_id.data and form.aws_secret_access_key.data and form.aws_session_token.data:
                session["aws_access_key_id"] = form.aws_access_key_id.data
                session["aws_secret_access_key"] = form.aws_secret_access_key.data
                session["aws_session_token"] = form.aws_session_token.data

                flash("Logged in successfully with AWS Academy credentials.", "success")
            else:
                flash("Please enter all AWS Academy credentials.", "danger")
                return render_template("student_login.html", form=form)

            return redirect(url_for("home"))

        except cognito_client.exceptions.UserNotConfirmedException:
            flash("Account not confirmed", "warning")
        except cognito_client.exceptions.NotAuthorizedException:
            flash("Invalid email or password", "danger")
        except ClientError as e:
            flash(e.response["Error"]["Message"], "danger")

    return render_template("student_login.html", form=form)




@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("choose_role"))


@app.route("/account", methods=["GET", "POST"])
def account():
    if "email" not in session:
        return redirect(url_for("choose_role"))

    form = UpdateAccountForm()

    if form.validate_on_submit():
        session["email"] = form.email.data
        flash("Account updated successfully.", "success")
        return redirect(url_for("account"))

    form.email.data = session.get("email", "")
    return render_template("account.html", form=form)


@app.route("/update_aws_credentials", methods=["POST"])
def update_aws_credentials():
    if "email" not in session:
        return redirect(url_for("choose_role"))

    role = session.get("role")

    if role == "Educator":
        aws_role_arn = request.form.get('aws_role_arn')
        print(f"DEBUG: Role ARN received: {aws_role_arn}")  # DEBUG

        if aws_role_arn:
            try:
                sts_client = boto3.client("sts")
                response = sts_client.assume_role(
                    RoleArn=aws_role_arn,
                    RoleSessionName="AppSession"
                )

                credentials = response["Credentials"]
                session["aws_access_key_id"] = credentials["AccessKeyId"]
                session["aws_secret_access_key"] = credentials["SecretAccessKey"]
                session["aws_session_token"] = credentials["SessionToken"]

                print(f"DEBUG: Credentials stored in session")  # DEBUG
                flash("AWS credentials updated.", "success")
            except ClientError as e:
                print(f"DEBUG: AWS Error: {e}")  # DEBUG
                flash(f"Error updating AWS credentials: {e.response['Error']['Message']}", "danger")
        else:
            print("DEBUG: No Role ARN provided")  # DEBUG
            flash("Please enter AWS Role ARN.", "danger")

    return redirect(url_for("account"))


@app.route("/templates")
def templates():
    categories = ["Web Servers", "Database Labs", "Security Labs", "Machine Learning"]
    templates_by_category = {}

    try:
        s3 = get_s3_client()

        for category in categories:
            response = s3.list_objects_v2(Bucket=TEMPLATES_BUCKET, Prefix=f"{category}/")

            templates = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    if not obj['Key'].endswith('/'):
                        name = obj['Key'].split('/')[-1].replace('.json', '')
                        templates.append({
                            'name': name,
                            'key': obj['Key'],
                            'size': obj['Size']
                        })

            templates_by_category[category] = templates

    except ClientError:
        flash("Could not load templates", "danger")
        templates_by_category = {}

    return render_template("templates.html", categories=categories, templates_by_category=templates_by_category)


@app.route("/templateupload", methods=["GET", "POST"])
def template_upload():
    categories = ["Web Servers", "Database Labs", "Security Labs", "Machine Learning"]

    if request.method == "POST":
        template_name = request.form.get('template_name')
        category = request.form.get('category_select')
        ami_id = request.form.get('ami_id')
        instance_type = request.form.get('instance_type')
        description = request.form.get('description', '')

        if not template_name or template_name == '':
            flash("Please enter a template name", "danger")
            return redirect(request.url)

        if template_name and category:
            try:
                template_data = {
                    "LaunchTemplateName": template_name,
                    "LaunchTemplateData": {
                        "ImageId": ami_id,
                        "InstanceType": instance_type,
                        "TagSpecifications": [
                            {
                                "ResourceType": "instance",
                                "Tags": [
                                    {"Key": "Name", "Value": template_name}
                                ]
                            }
                        ]
                    },
                    "Description": description,
                    "CreatedBy": session.get('email'),
                    "Category": category
                }

                filename = f"{template_name}.json"
                key = f"{category}/{filename}"

                s3 = get_s3_client()
                s3.put_object(
                    Bucket=TEMPLATES_BUCKET,
                    Key=key,
                    Body=json.dumps(template_data, indent=2),
                    ContentType='application/json'
                )

                flash("Template uploaded successfully", "success")
                return redirect(url_for('templates'))

            except ClientError:
                flash("Upload failed", "danger")

    return render_template("template_upload.html", categories=categories)


@app.route("/launch/<path:template_key>")
def launch_instance(template_key):
    try:
        # Get template from S3
        s3 = get_s3_client()
        template_obj = s3.get_object(Bucket=TEMPLATES_BUCKET, Key=template_key)
        template_data = json.loads(template_obj['Body'].read())

        # Get user's AWS credentials
        aws_access_key_id = session.get("aws_access_key_id")
        aws_secret_access_key = session.get("aws_secret_access_key")
        aws_session_token = session.get("aws_session_token")

        if not aws_access_key_id or not aws_secret_access_key:
            flash("Please configure your AWS credentials first", "warning")
            return redirect(url_for("account"))

        # Create EC2 client
        ec2 = boto3.client(
            'ec2',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name='us-east-1'
        )

        # Launch instance
        response = ec2.run_instances(
            ImageId=template_data['LaunchTemplateData']['ImageId'],
            InstanceType=template_data['LaunchTemplateData']['InstanceType'],
            MinCount=1,
            MaxCount=1,
            TagSpecifications=template_data['LaunchTemplateData']['TagSpecifications']
        )

        instance_id = response['Instances'][0]['InstanceId']
        flash(f"Instance {instance_id} launched successfully!", "success")

    except ClientError:
        flash("Failed to launch instance", "danger")
    except:
        flash("Could not launch instance", "danger")

    return redirect(url_for('templates'))


@app.route("/delete_template/<path:template_key>", methods=["POST"])
def delete_template(template_key):
    # Only educators can delete
    if session.get("role") != "Educator":
        flash("Only educators can delete templates", "danger")
        return redirect(url_for("templates"))

    try:
        s3 = get_s3_client()
        s3.delete_object(Bucket=TEMPLATES_BUCKET, Key=template_key)
        flash("Template deleted successfully", "success")
    except ClientError:
        flash("Failed to delete template", "danger")

    return redirect(url_for("templates"))



@app.route("/labs")
def labs():
    categories = ["Networking", "Databases", "Security", "Machine Learning"]
    labs_by_category = {}

    try:
        s3 = get_s3_client()

        for category in categories:
            response = s3.list_objects_v2(Bucket=LABS_BUCKET, Prefix=f"{category}/")

            labs = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    if not obj['Key'].endswith('/'):
                        name = obj['Key'].split('/')[-1]
                        labs.append({
                            'name': name,
                            'key': obj['Key'],
                            'size': obj['Size']
                        })

            labs_by_category[category] = labs

    except ClientError:
        flash("Could not load labs", "danger")
        labs_by_category = {}

    return render_template("labs.html", categories=categories, labs_by_category=labs_by_category)



@app.route("/labsupload", methods=["GET", "POST"])
def lab_upload():
    categories = ["Networking", "Databases", "Security", "Machine Learning"]

    if request.method == "POST":
        file = request.files.get('lab_file')
        category = request.form.get('category_select')

        if not file or file.filename == '':
            flash("Please select a file", "danger")
            return redirect(request.url)

        if file and category:
            try:
                filename = secure_filename(file.filename)
                key = f"{category}/{filename}"

                s3 = get_s3_client()
                s3.upload_fileobj(file, LABS_BUCKET, key)

                flash("Lab uploaded successfully", "success")
                return redirect(url_for('labs'))

            except ClientError:
                flash("Upload failed", "danger")

    return render_template("labs_upload.html", categories=categories)



@app.route("/view/<path:lab_key>")
def view_lab(lab_key):
    try:
        s3 = get_s3_client()
        url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': LABS_BUCKET,
                'Key': lab_key,
                'ResponseContentDisposition': 'inline',  # This makes it open in browser
                'ResponseContentType': 'application/pdf'  # This tells browser it's a PDF
            },
            ExpiresIn=3600
        )
        return redirect(url)
    except ClientError:
        flash("Can't view that file", "danger")
        return redirect(url_for('labs'))


@app.route("/delete_lab/<path:lab_key>", methods=["POST"])
def delete_lab(lab_key):
    # Only educators can delete
    if session.get("role") != "Educator":
        flash("Only educators can delete labs", "danger")
        return redirect(url_for("labs"))

    try:
        s3 = get_s3_client()
        s3.delete_object(Bucket=LABS_BUCKET, Key=lab_key)
        flash("Lab deleted successfully", "success")
    except ClientError:
        flash("Failed to delete lab", "danger")

    return redirect(url_for("labs"))



@app.route("/login-choice")
def login_choice():
    return render_template("choose_role.html")