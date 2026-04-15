# LearnSec

LearnSec is a cloud-based virtual machine management platform designed for students and educators undertaking cyber security and digital forensics modules at third level institutions.

## The Problem

Students undertaking practical cyber security and digital forensics lab work are traditionally required to install and configure virtual machine environments on their personal devices before lab sessions can begin. This process is time consuming, prone to human error, and heavily dependent on the hardware capabilities of each individual machine. Students with lower specification devices are frequently unable to run the required environments at all, creating an unequal learning experience across a class.

## The Solution

LearnSec removes these barriers entirely by hosting pre-configured virtual machine environments on AWS that students can launch and access through a standard web browser with a single click. No local installation or configuration is required on the student's device. Educators can manage the platform by uploading lab documentation and creating launch templates tailored to specific modules and class groups, while students can launch and connect to their virtual machines instantly through the browser using Apache Guacamole.

## Architecture

LearnSec is split across two AWS accounts to work around the limitations imposed by AWS Academy.

### The Problem with AWS Academy

AWS Academy is an educational programme that provides students and institutions with access to real AWS infrastructure through a sandboxed account. However, AWS Academy sessions expire after four hours, after which EC2 instances are automatically terminated. This means any services requiring persistence — such as user accounts and stored files — cannot be hosted in the Academy account without being lost at the end of each session.

### The Solution — Two Account Split

To address this, LearnSec uses two separate AWS accounts:

**Personal AWS Free Tier Account**
Hosts all services that require persistence across sessions:
- AWS Cognito — manages user authentication and stores student and educator accounts
- Amazon S3 (student-labs bucket) — stores lab instruction PDF files organised by category
- Amazon S3 (launch-templates bucket) — stores virtual machine launch template JSON files

**AWS Academy Account**
Hosts all compute infrastructure:
- EC2 Instance — runs the Flask web application on port 8081 and Apache Guacamole in Docker on port 8080
- Application Load Balancer — provides a stable public DNS address for the platform
- Target Groups — routes traffic to Flask and Guacamole on their respective ports
- Auto Scaling Group — maintains a minimum and maximum of one instance at all times, meaning when the four hour session expires and the instance is terminated, a new one is automatically launched from the launch template, keeping the platform available 24/7 without any manual intervention
- Security Group — allows inbound traffic on ports 22, 80, 8080, 8081, and 5901

### Guacamole and Docker

Apache Guacamole runs inside Docker containers on the EC2 instance itself. When the EC2 instance is set up, Docker and Docker Compose are installed on it, and Guacamole is deployed using the provided `docker-compose.yml` and `prepare.sh` scripts from the `guacamole` directory. This spins up the Guacamole service on port 8080 on the same instance that runs the Flask application. Because both services share the same machine, Flask can communicate with Guacamole internally via `http://localhost:8080/guacamole` without any traffic leaving the server.

## Guacamole and Flask Integration

One of the core features of LearnSec is the ability for students to connect to their running virtual machines directly through the browser. This is achieved by integrating Flask with Apache Guacamole through its REST API. The following steps describe exactly how this works:

### Step 1 — Student clicks Connect
When a student clicks connect on a running instance, the Flask route `/connect/<instance_id>` is triggered.

### Step 2 — Get the instance public IP
Flask uses the student's AWS Academy credentials stored in their session to call `ec2.describe_instances`, retrieving the public IP address of the running virtual machine.

### Step 3 — Authenticate with Guacamole
Flask makes an internal POST request to the Guacamole API running on the same EC2 instance at `http://localhost:8080/guacamole/api/tokens` using the guacadmin credentials, receiving back an authentication token. Because both Flask and Guacamole run on the same machine, this request never leaves the server.

### Step 4 — Remove existing connection
Flask checks the Guacamole PostgreSQL database for any existing connection with the same instance ID name and deletes it if found, preventing duplicate connections from building up over time.

### Step 5 — Create a new VNC connection
Flask creates a new VNC connection in Guacamole pointing to the instance public IP on port 5901 with the VNC password configured by the launch template user data script.

### Step 6 — Redirect the student
Flask base64 encodes the connection identifier in the format required by the Guacamole client URL and redirects the student directly to their virtual machine session, bypassing the Guacamole login page entirely.

### Student VM Setup
When a student instance boots, the user data script in the launch template automatically installs the XFCE desktop environment and TightVNC server, creates a student user, and starts a VNC server on port 5901, meaning the instance is ready to connect to as soon as it reaches a running state.

## Deployment

### Prerequisites
- A personal AWS free tier account
- An AWS Academy account
- Python 3.9 or higher
- AWS CDK installed
- Docker and Docker Compose installed on your EC2 instance

### Step 1 — Deploy Personal Account Infrastructure
In your personal AWS account, use the provided CDK stacks to deploy:
- AWS Cognito User Pool with Student and Educator groups
- S3 bucket for lab documents
- S3 bucket for launch templates

```bash
cd aws_personal
cdk deploy AuthStack
cdk deploy LabsStack
cdk deploy TemplatesStack
```
or 
```bash
cd aws_personal
cdk deploy --all
```
Note the Cognito User Pool ID and Client ID from the CDK output.

### Step 2 — Launch EC2 Instance in AWS Academy
In your AWS Academy account:
- Launch a t3.micro EC2 instance using Amazon Linux 2023
- Attach a security group allowing inbound traffic on ports 22, 80, 8080, 8081 and 5901
- Configure an Application Load Balancer with two target groups, one for Flask on port 8081 and one for Guacamole on port 8080
- Configure an Auto Scaling Group with a minimum and maximum of 1 using a launch template pointing to your instance configuration

### Step 3 — Deploy Guacamole
SSH into your EC2 instance and run:

```bash
cd guacamole
bash prepare.sh
docker-compose up -d
```

This installs and starts Guacamole inside Docker containers on the instance, making it available internally on port 8080.

### Step 4 — Deploy the Flask Application
SSH into your EC2 instance and run:

```bash
export FLASK_APP=pythonflaskwebapp
export COGNITO_USER_POOL_ID=your_pool_id
export COGNITO_CLIENT_ID=your_client_id
export LABS_BUCKET_NAME=your_labs_bucket
export TEMPLATES_BUCKET_NAME=your_templates_bucket
export AWS_ACCESS_KEY_ID=your_academy_key
export AWS_SECRET_ACCESS_KEY=your_academy_secret
export AWS_SESSION_TOKEN=your_academy_token

nohup python3 -m flask run --host=0.0.0.0 --port=8081 > ~/flask.log 2>&1 &
```

### Step 5 — Access the Platform
Navigate to your Application Load Balancer DNS address in any web browser. No additional software or configuration is required on the student's device.