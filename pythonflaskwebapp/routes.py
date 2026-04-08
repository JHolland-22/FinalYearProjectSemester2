import json
import base64
from flask import render_template, url_for, flash, redirect, request, session
from werkzeug.utils import secure_filename
from datetime import datetime
from .aws_utils import get_s3_client, ec2_client_from_session, get_s3_read_client
from botocore.exceptions import ClientError
import boto3
import os
import re
from . import app
from .forms import (
    RegistrationForm,
    LoginForm,
    ConfirmForm
)
import requests

# AWS config pulled from environment variables
AWS_REGION = os.environ.get("AWS_REGION")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")
LABS_BUCKET = os.environ.get('LABS_BUCKET_NAME')
TEMPLATES_BUCKET = os.environ.get('TEMPLATES_BUCKET_NAME')

# AWS clients
cognito_client = boto3.client("cognito-idp", region_name=AWS_REGION)
ec2 = boto3.client("ec2", region_name="us-east-1")



# Adds a lab activity entry to the session history (used on the dashboard to show recently viewed/launched labs)
def log_recent_activity(name):
    recent = session.get('recent_labs', [])
    recent.insert(0, {
        'name': name,
        'time': datetime.now().strftime('%d/%m/%Y %H:%M')
    })
    session['recent_labs'] = recent[:5] # Keeps only the 5 most recent entries so the session doesn't grow indefinitely
    session.modified = True



# Main dashboard route — accessible via both "/" and "/dashboard"
# Redirects to role selection if the user isn't logged in
# If AWS credentials are in the session, fetches the user's EC2 instances and counts their states
# Also pulls recent lab activity from the session to display on the dashboard
@app.route("/")
@app.route("/dashboard")
def dashboard():
    if "email" not in session:
        return redirect(url_for("choose_role"))

    if "login_time" not in session:
        session["login_time"] = datetime.now().isoformat()

    # Get instance data if credentials are available
    instances = []
    running_count = 0
    stopped_count = 0
    if session.get("aws_access_key_id"):
        try:
            ec2 = boto3.client(
                'ec2',
                aws_access_key_id=session["aws_access_key_id"],
                aws_secret_access_key=session["aws_secret_access_key"],
                aws_session_token=session.get("aws_session_token"),
                region_name='us-east-1'
            )
            response = ec2.describe_instances()
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    state = instance['State']['Name']
                    name = "Unnamed"
                    for tag in instance.get('Tags', []):
                        if tag['Key'] == 'Name':
                            name = tag['Value']
                    instances.append({
                        'id': instance['InstanceId'],
                        'name': name,
                        'state': state,
                        'type': instance['InstanceType'],
                        'launch_time': instance['LaunchTime'].strftime('%d/%m/%Y %H:%M')
                    })
                    if state == 'running':
                        running_count += 1
                    elif state == 'stopped':
                        stopped_count += 1
        except Exception as e:
            print(f"DASHBOARD ERROR: {str(e)}")

    # Get recent labs viewed
    recent_labs = session.get('recent_labs', [])

    return render_template("dashboard.html",
                           instances=instances,
                           running_count=running_count,
                           stopped_count=stopped_count,
                           total_instances=len(instances),
                           recent_labs=recent_labs)







# About page has the poster I created for the expo
@app.route("/about")
def about():
    return render_template("about.html", title="About")





# Fetches and displays all EC2 instances for the logged-in user
# Requires a valid session and AWS credentials, redirects if either are missing
@app.route("/instances")
def instances():
    if "email" not in session:
        return redirect(url_for("choose_role"))

    if not session.get("aws_access_key_id"):
        flash("Please configure your AWS credentials first", "warning")
        return redirect(url_for("account"))

    try:
        # Build EC2 client using the AWS Academy credentials stored in the session
        ec2 = boto3.client(
            'ec2',
            aws_access_key_id=session["aws_access_key_id"],
            aws_secret_access_key=session["aws_secret_access_key"],
            aws_session_token=session.get("aws_session_token"),
            region_name='us-east-1'
        )

        response = ec2.describe_instances()
        instances = []

        # AWS groups instances inside Reservations, so both loops are needed to reach each instance
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                name = "Unnamed"
                # Instance names are stored as tags, not a direct property
                for tag in instance.get('Tags', []):
                    if tag['Key'] == 'Name':
                        name = tag['Value']

                # Store only the fields needed for the instances page
                instances.append({
                    'id': instance['InstanceId'],
                    'name': name,
                    'state': instance['State']['Name'],
                    'type': instance['InstanceType']
                })

        return render_template("instances.html", instances=instances)

    except:
        # If the EC2 call fails, render the page with an empty list rather than crashing
        return render_template("instances.html", instances=[])








# Starts a stopped EC2 instance by ID, then redirects back to the instances page
@app.route("/start_instance/<instance_id>")
def start_instance(instance_id):
    if "email" not in session:
        return redirect(url_for("choose_role"))

    # Build EC2 client using the AWS Academy credentials stored in the session
    ec2 = boto3.client(
        'ec2',
        aws_access_key_id=session["aws_access_key_id"],
        aws_secret_access_key=session["aws_secret_access_key"],
        aws_session_token=session.get("aws_session_token"),
        region_name='us-east-1'
    )

    # instance_id is passed in from the URL and wrapped in a list as the API expects a list of IDs
    ec2.start_instances(InstanceIds=[instance_id])
    return redirect(url_for('instances'))








# Stops a running EC2 instance by ID, then redirects back to the instances page
@app.route("/stop_instance/<instance_id>")
def stop_instance(instance_id):
    if "email" not in session:
        return redirect(url_for("choose_role"))

    # Build EC2 client using the AWS Academy credentials stored in the session
    ec2 = boto3.client(
        'ec2',
        aws_access_key_id=session["aws_access_key_id"],
        aws_secret_access_key=session["aws_secret_access_key"],
        aws_session_token=session.get("aws_session_token"),
        region_name='us-east-1'
    )

    # instance_id is passed in from the URL and wrapped in a list as the API expects a list of IDs
    ec2.stop_instances(InstanceIds=[instance_id])
    return redirect(url_for('instances'))







# Handles new user registration via AWS Cognito
# Automatically assigns a role based on email format, numeric prefix = Student, anything else = Educator
@app.route("/register", methods=["GET", "POST"])
def register():
    # Redirect logged-in users to dashboard
    if session.get("email"):
        return redirect(url_for("dashboard"))

    form = RegistrationForm()

    if form.validate_on_submit():
        # Student emails use a numeric ID as the prefix e.g. 20012345@setu.ie or 20012345@mail.wit.ie
        identifier, _, _ = form.email.data.partition('@')
        role = "Student" if re.fullmatch(r'\d+', identifier) else "Educator"

        try:
            # Register the user in Cognito with their role and class group as custom attributes
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

        # On success Cognito sends a confirmation code to the user's email
        flash("A confirmation code has been sent to your email.", "info")
        return redirect(url_for("confirm", email=form.email.data))

    return render_template("register.html", form=form)










# Handles email confirmation after registration using the code Cognito sends to the user
# Pre-fills the email field when an email address is passed in from the register page
@app.route("/confirm", methods=["GET", "POST"])
def confirm():
    form = ConfirmForm()
    if request.method == "GET":
        # Pre-fill the email field using the value passed in the URL
        form.email.data = request.args.get("email")

    if form.validate_on_submit():
        if form.resend.data:
            # User clicked resend, request a new confirmation code from Cognito
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
            # Submit the confirmation code entered by the user to complete account verification
            cognito_client.confirm_sign_up(
                ClientId=COGNITO_CLIENT_ID,
                Username=form.email.data,
                ConfirmationCode=form.code.data,
            )
        except Exception as e:
            flash(f"Confirmation failed: {e}", "danger")
            return render_template("confirm.html", form=form)

        # After successful confirmation, send the user to the login page with the email carried over
        return redirect(url_for("choose_role", email=form.email.data))

    return render_template("confirm.html", form=form)











# Displays the page where the user chooses how to log in
@app.route("/choose_role", methods=["GET"])
def choose_role():
    return render_template("choose_role.html")









# Handles educator login using AWS Cognito authentication
# Stores user details and AWS credentials in the session for later use
@app.route("/educator_login", methods=["GET", "POST"])
def educator_login():
    if session.get("email"):
        return redirect(url_for("dashboard"))

    form = LoginForm()

    if form.validate_on_submit():
        try:
            # Authenticate user with Cognito using email and password
            cognito_response = cognito_client.initiate_auth(
                ClientId=COGNITO_CLIENT_ID,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": form.email.data,
                    "PASSWORD": form.password.data,
                },
            )

            # Reset session and store basic user info
            session.clear()
            session["email"] = form.email.data
            session["role"] = "Educator"

            try:
                # Retrieve additional user attributes (e.g. class group) from Cognito
                user_response = cognito_client.get_user(
                    AccessToken=cognito_response['AuthenticationResult']['AccessToken']
                )

                class_group = None
                for attr in user_response['UserAttributes']:
                    if attr['Name'] == 'custom:class_group':
                        class_group = attr['Value']
                        break

                session["class_group"] = class_group
            except Exception as e:

                # If attribute retrieval fails, continue without class group
                session["class_group"] = None

            # Store AWS Academy credentials if all fields are provided
            if form.aws_access_key_id.data and form.aws_secret_access_key.data and form.aws_session_token.data:
                session["aws_access_key_id"] = form.aws_access_key_id.data
                session["aws_secret_access_key"] = form.aws_secret_access_key.data
                session["aws_session_token"] = form.aws_session_token.data
                flash("Logged in successfully.", "success")
            else:
                flash("Please enter all AWS Academy credentials.", "danger")
                return render_template("educator_login.html", form=form)

            return redirect(url_for("dashboard"))

        except cognito_client.exceptions.UserNotConfirmedException:
            flash("Account not confirmed", "warning")
        except cognito_client.exceptions.NotAuthorizedException:
            flash("Invalid email or password", "danger")
        except ClientError as e:
            flash(e.response["Error"]["Message"], "danger")

    return render_template("educator_login.html", form=form)








# Handles student login using AWS Cognito authentication
# Stores user details and AWS Academy credentials in the session
@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    if session.get("email"):
        return redirect(url_for("dashboard"))

    form = LoginForm()

    if form.validate_on_submit():
        try:
            # Authenticate user with Cognito using email and password
            cognito_response = cognito_client.initiate_auth(
                ClientId=COGNITO_CLIENT_ID,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": form.email.data,
                    "PASSWORD": form.password.data,
                },
            )

            # Reset session and store basic user info
            session.clear()
            session["email"] = form.email.data
            session["role"] = "Student"

            try:
                # Retrieve class group attribute from Cognito
                user_response = cognito_client.get_user(
                    AccessToken=cognito_response['AuthenticationResult']['AccessToken']
                )

                class_group = None
                for attr in user_response['UserAttributes']:
                    if attr['Name'] == 'custom:class_group':
                        class_group = attr['Value']
                        break

                session["class_group"] = class_group
            except Exception as e:
                # Continue without class group if retrieval fails
                session["class_group"] = None

            # Store AWS Academy credentials provided by the student
            if form.aws_access_key_id.data and form.aws_secret_access_key.data and form.aws_session_token.data:
                session["aws_access_key_id"] = form.aws_access_key_id.data
                session["aws_secret_access_key"] = form.aws_secret_access_key.data
                session["aws_session_token"] = form.aws_session_token.data

                flash("Logged in successfully with AWS Academy credentials.", "success")
            else:
                flash("Please enter all AWS Academy credentials.", "danger")
                return render_template("student_login.html", form=form)

            return redirect(url_for("dashboard"))

        except cognito_client.exceptions.UserNotConfirmedException:
            flash("Account not confirmed", "warning")
        except cognito_client.exceptions.NotAuthorizedException:
            flash("Invalid email or password", "danger")
        except ClientError as e:
            flash(e.response["Error"]["Message"], "danger")

    return render_template("student_login.html", form=form)










# Logs the user out by clearing the session and redirecting to the choose role page
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("choose_role"))







# Displays the account page for the logged-in user
# Redirects to login if no active session exists
@app.route("/account", methods=["GET"])
def account():
    if "email" not in session:
        return redirect(url_for("choose_role"))

    return render_template("account.html")










# Updates AWS credentials stored in the session from the account form
# Used when a user adds or refreshes their AWS Academy credentials
@app.route("/update_aws_credentials", methods=["POST"])
def update_aws_credentials():
    if "email" not in session:
        return redirect(url_for("choose_role"))

    # Retrieve credentials submitted from the form
    aws_access_key_id = request.form.get('aws_access_key_id')
    aws_secret_access_key = request.form.get('aws_secret_access_key')
    aws_session_token = request.form.get('aws_session_token')


    if aws_access_key_id and aws_secret_access_key:
        # Store credentials in session for use in AWS API calls
        session["aws_access_key_id"] = aws_access_key_id
        session["aws_secret_access_key"] = aws_secret_access_key
        session["aws_session_token"] = aws_session_token
        # Update login time to track when credentials were last set
        session["login_time"] = datetime.now().isoformat()
        flash("AWS credentials updated.", "success")
    else:
        flash("Please enter Access Key ID and Secret Access Key.", "danger")
    return redirect(url_for("account"))













# Retrieves and displays available templates from S3
# Filters templates based on user role and class group
@app.route("/templates")
def templates():
    templates = []
    user_class_group = session.get('class_group')
    is_educator = session.get('role') == 'Educator'

    try:
        # Create S3 client for reading template files
        s3 = get_s3_read_client()
        response = s3.list_objects_v2(Bucket=TEMPLATES_BUCKET)

        if 'Contents' in response:
            for obj in response['Contents']:
                if not obj['Key'].endswith('/'):
                    try:
                        # Load template JSON data from S3
                        template_obj = s3.get_object(Bucket=TEMPLATES_BUCKET, Key=obj['Key'])
                        template_data = json.loads(template_obj['Body'].read())
                        template_class_group = template_data.get('ClassGroup')

                        # Allow access if educator, matching class group, or marked as "All"
                        if is_educator or template_class_group == user_class_group or template_class_group == "All":

                            # Extract clean template name from S3 key
                            name = obj['Key'].split('/')[-1].replace('.json', '') if '/' in obj['Key'] else obj[
                                'Key'].replace('.json', '')

                            # Store only required fields for display
                            templates.append({
                                'name': name,
                                'key': obj['Key'],
                                'size': obj['Size'],
                                'description': template_data.get('Description', '')
                            })
                    except:
                        # Skip files that fail to load or parse
                        pass

    except ClientError:
        # Handle failure to connect to or read from S3
        flash("Could not load templates", "danger")
        templates = []

    return render_template("templates.html", templates=templates)













# Launches a new EC2 instance using a selected template stored in S3
# Reads template configuration, applies user AWS credentials, and starts the instance
@app.route("/launch/<path:template_key>")
def launch_instance(template_key):
    try:
        # Load template JSON from S3
        s3 = get_s3_read_client()
        template_obj = s3.get_object(Bucket=TEMPLATES_BUCKET, Key=template_key)
        template_data = json.loads(template_obj["Body"].read())

        # Retrieve AWS credentials from session
        aws_access_key_id = session.get("aws_access_key_id")
        aws_secret_access_key = session.get("aws_secret_access_key")
        aws_session_token = session.get("aws_session_token")

        if not aws_access_key_id or not aws_secret_access_key:
            flash("Please configure your AWS credentials first", "warning")
            return redirect(url_for("account"))

        # Create EC2 client using user credentials
        ec2 = boto3.client(
            "ec2",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name="us-east-1",
        )

        # Build parameters for instance launch from template data
        launch_params = {
            "ImageId": template_data["LaunchTemplateData"]["ImageId"],
            "InstanceType": template_data["LaunchTemplateData"]["InstanceType"],
            "MinCount": 1,
            "MaxCount": 1,
        }

        # EC2 requires UserData to be base64 encoded
        user_data = template_data["LaunchTemplateData"].get("UserData", "")
        if user_data:
            launch_params["UserData"] = base64.b64encode(user_data.encode()).decode()

        # Launch the EC2 instance
        response = ec2.run_instances(**launch_params)
        instance_id = response["Instances"][0]["InstanceId"]
        try:
            # Add a Name tag to the instance for easier identification
            ec2.create_tags(Resources=[instance_id],
                            Tags=[{"Key": "Name", "Value": template_data["LaunchTemplateName"]}])
        except:
            # Tagging is optional, continue if it fails
            pass

        # Record activity for dashboard display
        log_recent_activity(f"Launched: {template_data['LaunchTemplateName']}")

        flash(f"Instance {instance_id} launched successfully!", "success")

    except Exception as e:
        print(f"LAUNCH ERROR: {str(e)}")
        flash("Failed to launch instance", "danger")

    return redirect(url_for("instances"))












# Creates a Guacamole VNC connection for the selected EC2 instance
# Looks up the instance public IP, registers a connection in Guacamole, then redirects the user to the remote session
@app.route("/connect/<instance_id>")
def connect_vnc(instance_id):
    try:
        # Retrieve AWS credentials from session and build EC2 client
        aws_access_key_id = session.get("aws_access_key_id")
        aws_secret_access_key = session.get("aws_secret_access_key")
        aws_session_token = session.get("aws_session_token")

        ec2 = ec2_client_from_session(aws_access_key_id, aws_secret_access_key, aws_session_token)

        # Look up the selected instance so its public IP can be used for the VNC connection
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        public_ip = instance.get('PublicIpAddress')

        if not public_ip:
            flash("Instance has no public IP address", "warning")
            return redirect(url_for('instances'))

        # Internal Guacamole service used to create and manage remote desktop connections
        guac_internal = "http://localhost:8080/guacamole"

        # Authenticate with Guacamole API to get a session token
        token_resp = requests.post(f"{guac_internal}/api/tokens", data={"username": "guacadmin", "password": "guacadmin"})
        token = token_resp.json()["authToken"]

        # Build a unique Guacamole connection name for this EC2 instance
        connection_name = f"instance-{instance_id}"
        connection_data = {
            "parentIdentifier": "ROOT",
            "name": connection_name,
            "protocol": "vnc",
            "parameters": {
                "hostname": public_ip,
                "port": "5901",
                "password": "kali"
            },
            "attributes": {
                "max-connections": "",
                "max-connections-per-user": ""
            }
        }

        # Remove any existing connection with the same name to avoid duplicate entries in Guacamole
        existing = requests.get(f"{guac_internal}/api/session/data/postgresql/connections", params={"token": token})
        if existing.status_code == 200:
            for conn_id, conn in existing.json().items():
                if conn.get("name") == connection_name:
                    requests.delete(f"{guac_internal}/api/session/data/postgresql/connections/{conn_id}", params={"token": token})
                    break


        # Create a new Guacamole connection for the selected instance
        create_resp = requests.post(f"{guac_internal}/api/session/data/postgresql/connections", json=connection_data, params={"token": token})
        conn_id = create_resp.json()["identifier"]

        # Guacamole expects the client ID in base64 format: "connection_id\\0c\\0postgresql"
        client_id = base64.b64encode(f"{conn_id}\0c\0postgresql".encode()).decode()

        # Extract server IP (removes Flask port) and redirect to Guacamole client using client_id (connection) and token (authentication)
        server_ip = request.host.split(":")[0]
        return redirect(f"http://{server_ip}:8080/guacamole/#/client/{client_id}?token={token}")

    except Exception as e:
        flash(f"Failed to connect: {str(e)}", "danger")
        return redirect(url_for('instances'))










# Handles creation and upload of launch templates to S3
# Validates form input, builds template JSON, and stores it for later instance launches
@app.route("/templateupload", methods=["GET", "POST"])
def template_upload():
    if request.method == "POST":
        # Retrieve form data submitted by the user
        template_name = request.form.get('template_name')
        ami_id = request.form.get('ami_id')
        instance_type = request.form.get('instance_type')
        description = request.form.get('description', '')
        share_with = request.form.get('share_with')
        user_data = request.form.get('user_data', '')

        print(f"DEBUG: Got form data - name:'{template_name}', ami:'{ami_id}'")

        # Basic validation to ensure required fields are provided
        if not template_name or template_name == '':
            flash("Please enter a template name", "danger")
            return redirect(request.url)

        if not ami_id or ami_id == '':
            flash("Please enter an AMI ID", "danger")
            return redirect(request.url)

        if not description or description == '':
            flash("Please enter a description", "danger")
            return redirect(request.url)

        try:
            # Build launch template structure used for EC2 instance creation
            template_data = {
                "LaunchTemplateName": template_name,
                "LaunchTemplateData": {
                    "ImageId": ami_id,
                    "InstanceType": instance_type,
                },
                "Description": description,
                "CreatedBy": session.get('email'),
                "ClassGroup": share_with
            }

            # Add user data if provided (optional)
            if user_data:
                template_data["LaunchTemplateData"]["UserData"] = user_data

            # Use template name as the S3 file key
            filename = f"{template_name}.json"
            print(f"DEBUG: S3 key will be: {filename}")

            # Upload launch template JSON to S3 bucket
            s3 = get_s3_client()
            s3.put_object(
                Bucket=TEMPLATES_BUCKET,
                Key=filename,
                Body=json.dumps(template_data, indent=2),
                ContentType='application/json'
            )
            flash("Template uploaded successfully", "success")
            return redirect(url_for('templates'))

        except Exception as e:
            # Handle upload failure without exposing internal errors
            flash("Upload failed", "danger")

    return render_template("template_upload.html")











# Allows educators to edit existing launch templates stored in S3
# Loads template data into a form (GET) and updates it in S3 (POST)
@app.route("/edit_template/<path:template_key>", methods=["GET", "POST"])
def edit_template(template_key):
    # Restrict access to educators only
    if session.get("role") != "Educator":
        flash("Only educators can edit templates", "danger")
        return redirect(url_for("templates"))

    if request.method == "GET":
        try:
            # Load existing template data from S3
            s3 = get_s3_client()
            template_obj = s3.get_object(Bucket=TEMPLATES_BUCKET, Key=template_key)
            template_data = json.loads(template_obj['Body'].read())

            # Pre-fill form fields with existing template values
            form_data = {
                'template_name': template_data['LaunchTemplateName'],
                'ami_id': template_data['LaunchTemplateData']['ImageId'],
                'instance_type': template_data['LaunchTemplateData']['InstanceType'],
                'description': template_data.get('Description', ''),
                'share_with': template_data.get('ClassGroup', ''),
                'user_data': template_data['LaunchTemplateData'].get('UserData', '')
            }

            return render_template("template_upload.html", form_data=form_data, edit_mode=True,
                                   template_key=template_key)

        except:
            # Handle failure to load template from S3
            flash("Could not load template", "danger")
            return redirect(url_for("templates"))

    # POST - Update template (same logic as template_upload but save to existing key)
    template_name = request.form.get('template_name')
    ami_id = request.form.get('ami_id')
    instance_type = request.form.get('instance_type')
    description = request.form.get('description', '')
    share_with = request.form.get('share_with')
    user_data = request.form.get('user_data', '')

    try:
        # Rebuild launch template structure with updated values
        template_data = {
            "LaunchTemplateName": template_name,
            "LaunchTemplateData": {
                "ImageId": ami_id,
                "InstanceType": instance_type,
            },
            "Description": description,
            "CreatedBy": session.get('email'),
            "ClassGroup": share_with
        }

        # Include optional user data if provided
        if user_data:
            template_data["LaunchTemplateData"]["UserData"] = user_data

        # Overwrite existing template in S3 using the same key
        s3 = get_s3_client()
        s3.put_object(
            Bucket=TEMPLATES_BUCKET,
            Key=template_key,
            Body=json.dumps(template_data, indent=2),
            ContentType='application/json'
        )

        flash("Template updated successfully", "success")
        return redirect(url_for('templates'))

    except Exception as e:
        # Handle update failure
        flash("Failed to update template", "danger")
        return redirect(url_for("templates"))












# Allows educators to delete a launch template from S3
# Removes the template file using its key and redirects back to the templates page
@app.route("/delete_template/<path:template_key>", methods=["POST"])
def delete_template(template_key):
    # Restrict deletion to educators only
    if session.get("role") != "Educator":
        flash("Only educators can delete templates", "danger")
        return redirect(url_for("templates"))

    try:
        # Delete the template object from the S3 bucket
        s3 = get_s3_client()
        s3.delete_object(Bucket=TEMPLATES_BUCKET, Key=template_key)
        flash("Template deleted successfully", "success")

    except ClientError:
        # Handle failure to delete from S3
        flash("Failed to delete template", "danger")

    return redirect(url_for("templates"))











# Retrieves and displays labs from S3, grouped by category
# Each category corresponds to a folder prefix in the S3 bucket
@app.route("/labs")
def labs():
    categories = ["Networking", "Databases", "Security", "Machine Learning"]
    labs_by_category = {}

    try:
        # Create S3 client for reading lab files
        s3 = get_s3_read_client()

        # Loop through each category and fetch its labs from S3
        for category in categories:
            response = s3.list_objects_v2(Bucket=LABS_BUCKET, Prefix=f"{category}/")

            labs = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Skip S3 folder placeholders (keys ending with '/'), only include actual lab files
                    if not obj['Key'].endswith('/'):
                        # Extract lab file name from S3 key
                        name = obj['Key'].split('/')[-1]
                        # Store lab details for display
                        labs.append({
                            'name': name,
                            'key': obj['Key'],
                            'size': obj['Size']
                        })

            # Store labs under their category
            labs_by_category[category] = labs

    except ClientError:
        # Handle failure to load labs from S3
        flash("Could not load labs", "danger")
        labs_by_category = {}

    return render_template("labs.html", categories=categories, labs_by_category=labs_by_category)












# Handles upload of lab files to S3 under a selected category
# Files are stored using category-based prefixes for organisation
@app.route("/labsupload", methods=["GET", "POST"])
def lab_upload():
    categories = ["Networking", "Databases", "Security", "Machine Learning"]

    if request.method == "POST":
        # Get uploaded file and selected category from the form
        file = request.files.get('lab_file')
        category = request.form.get('category_select')

        # Check a file was selected
        if not file or file.filename == '':
            flash("Please select a file", "danger")
            return redirect(request.url)

        if file and category:
            try:
                # Clean filename to remove unsafe characters and build S3 key
                filename = secure_filename(file.filename)
                key = f"{category}/{filename}"

                # Upload the file to S3
                s3 = get_s3_client()
                s3.upload_fileobj(file, LABS_BUCKET, key)

                flash("Lab uploaded successfully", "success")
                return redirect(url_for('labs'))

            except ClientError:
                # Show error if upload fails
                flash("Upload failed", "danger")

    return render_template("labs_upload.html", categories=categories)











# Generates a temporary S3 URL to view a lab file in the browser
# Also logs the activity for display on the dashboard
@app.route("/view/<path:lab_key>")
def view_lab(lab_key):
    try:
        s3 = get_s3_client()

        # Record that this lab was viewed
        log_recent_activity(f"Viewed lab: {lab_key.split('/')[-1]}")

        # Create a temporary URL to access the file directly from S3
        url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': LABS_BUCKET,
                'Key': lab_key,
                'ResponseContentDisposition': 'inline',  # This makes it open in browser
                'ResponseContentType': 'application/pdf'  # This tells browser it's a PDF
            },
            ExpiresIn=3600 # URL expires after 1 hour
        )
        return redirect(url)
    except ClientError:
        # Handle failure to generate or access the file
        flash("Can't view that file", "danger")
        return redirect(url_for('labs'))














# Allows educators to delete a lab file from S3
# Removes the file using its key and redirects back to the labs page
@app.route("/delete_lab/<path:lab_key>", methods=["POST"])
def delete_lab(lab_key):
    # Restrict deletion to educators only
    if session.get("role") != "Educator":
        flash("Only educators can delete labs", "danger")
        return redirect(url_for("labs"))

    try:
        # Delete the lab file from the S3 bucket
        s3 = get_s3_client()
        s3.delete_object(Bucket=LABS_BUCKET, Key=lab_key)
        flash("Lab deleted successfully", "success")

    except ClientError:
        # Handle failure to delete from S3
        flash("Failed to delete lab", "danger")

    return redirect(url_for("labs"))