## Deployment

### What You Need
- A personal AWS free tier account
- An AWS Academy account
- Python 3.9 or higher
- AWS CDK installed
- Docker and Docker Compose installed on your EC2 instance

### Step 1 - Deploy the Personal Account Infrastructure
In your personal AWS account, deploy the CDK stacks:

```bash
cd aws_personal
cd aws
cdk deploy --all
```

### Step 2 - Set Up the EC2 Instance in AWS Academy
In your AWS Academy account:
- Launch a t3.micro EC2 instance using Amazon Linux 2023
- Create a key pair and download the .pem file so you can SSH into the instance
- Attach a security group allowing ports 22, 80, 8080, 8081, and 5901
- Set up an Application Load Balancer with two target groups, one for Flask on port 8081 and one for Guacamole on port 8080
- Create an Auto Scaling Group with min and max set to 1 using a launch template for your instance

### Step 3 - Transfer the Project to the Instance
You can either SCP the project folder from your local machine or clone the repo directly on the instance.

**Option 1 - SCP from your local machine:**
```bash
chmod 400 ~/Downloads/your-key.pem
scp -i ~/Downloads/your-key.pem -r /path/to/FinalYearProjectSemester2 ec2-user@YOUR-INSTANCE-IP:/home/ec2-user/
```

**Option 2 - Clone the repo on the instance:**
```bash
ssh -i ~/Downloads/your-key.pem ec2-user@YOUR-INSTANCE-IP
git clone https://github.com/YOUR-USERNAME/FinalYearProjectSemester2.git
```

Then install the Python dependencies:
```bash
cd FinalYearProjectSemester2/pythonflaskwebapp
pip3 install -r requirements.txt
```

### Step 4 - Start Guacamole
SSH into the instance and run:

```bash
cd FinalYearProjectSemester2/guacamole
bash prepare.sh
docker-compose up -d
```

### Step 5 - Start Flask
Still on the instance, set the environment variables and start the app:

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

### Step 6 - Open the Platform
Go to your Application Load Balancer DNS address in any browser.