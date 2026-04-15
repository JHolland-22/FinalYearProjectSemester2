import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional




# Form used for user registration
# Collects basic user details and determines role based on email format
class RegistrationForm(FlaskForm):
    # AWS account ID must be exactly 12 characters
    aws_account_id = StringField(
        'AWS Account ID',
        validators=[DataRequired(), Length(min=12, max=12)]
    )

    # Email field with standard email validation
    email = StringField(
        'Email',
        validators=[DataRequired(), Email()]
    )

    # Dropdown for selecting class group
    class_group = SelectField(
        'Class Group',
        choices=[
            ('', 'Select your class'),
            ('devops', 'DevOps'),
            ('cloud', 'Cloud Computing'),
            ('network_security', 'Network Security')
        ],
        validators=[DataRequired()]
    )

    # Password input
    password = PasswordField(
        'Password',
        validators=[DataRequired()]
    )
    # Re-enter password has to be the same as the one entered in already
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('password')]
    )
    submit = SubmitField('Sign Up')
    # Role is set based on email format
    role = None

    # Custom validation for email - to make sure it's the right institutions emails and for student and educator
    def validate_email(self, email):
        allowed_domains = ['gmail.com', 'setu.ie', 'mail.wit.ie']
        # Split email into prefix and domain
        identifier, _, domain = email.data.partition('@')

        # Check domain is allowed
        if domain not in allowed_domains:
            raise ValidationError('Email must be a valid college email (@setu.ie or @mail.wit.ie)')

        # If prefix is only numbers → student
        if re.fullmatch(r'\d+', identifier):
            self.role = 'student'

        # If prefix is letters (or dots) → educator
        elif re.fullmatch(r'[a-zA-Z.]+', identifier):
            self.role = 'educator'
        # Anything else is invalid
        else:
            raise ValidationError('Email prefix must be numbers (students) or letters (educators)')






# Form used to confirm account using code sent by Cognito
class ConfirmForm(FlaskForm):
    # User email
    email = StringField('Email', validators=[DataRequired(), Email()])
    # Confirmation Code must be 6 characters
    code = StringField('Confirmation Code', validators=[DataRequired(), Length(min=6, max=6)])
    # Button to request a new code
    resend = SubmitField('Resend Code')
    # Button to confirm account
    submit = SubmitField('Confirm Account')







# Form used for both student and educator login
class LoginForm(FlaskForm):
    # Standard login fields
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])

    # AWS credentials provided by user (used for EC2/S3 access)
    aws_access_key_id = StringField('AWS Access Key ID')
    aws_secret_access_key = PasswordField('AWS Secret Access Key')
    aws_session_token = TextAreaField('AWS Session Token')
    submit = SubmitField('Login')





