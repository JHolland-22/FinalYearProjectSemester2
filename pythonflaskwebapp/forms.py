import re
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from flask_login import current_user
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional
##from .models import User

class RegistrationForm(FlaskForm):
    aws_account_id = StringField(
        'AWS Account ID',
        validators=[DataRequired(), Length(min=12, max=12)]
    )
    email = StringField(
        'Email',
        validators=[DataRequired(), Email()]
    )
    password = PasswordField(
        'Password',
        validators=[DataRequired()]
    )
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('password')]
    )
    submit = SubmitField('Sign Up')
    role = None  # Will be determined based on email prefix

    def validate_email(self, email):
        allowed_domains = ['gmail.com', 'setu.ie', 'mail.wit.ie']
        identifier, _, domain = email.data.partition('@')

        if domain not in allowed_domains:
            raise ValidationError('Email must be a valid college email (@setu.ie or @mail.wit.ie)')

        if re.fullmatch(r'\d+', identifier):
            self.role = 'student'
        elif re.fullmatch(r'[a-zA-Z.]+', identifier):
            self.role = 'educator'
        else:
            raise ValidationError('Email prefix must be numbers (students) or letters (educators)')


class ConfirmForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    code = StringField('Confirmation Code', validators=[DataRequired(), Length(min=6, max=6)])
    resend = SubmitField('Resend Code')
    submit = SubmitField('Confirm Account')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    aws_role_arn = StringField('AWS Role ARN', validators=[DataRequired()])
    aws_external_id = StringField('AWS External ID', validators=[DataRequired()])
    aws_session_name = StringField('AWS Session Name', validators=[Optional()])
    submit = SubmitField('Login')



class UpdateAccountForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Update')


class AmiShareForm(FlaskForm):
    ami_id = StringField("AMI Image ID", validators=[DataRequired()])
    account_ids = StringField("AWS Account IDs")
    submit = SubmitField("Share AMI")
