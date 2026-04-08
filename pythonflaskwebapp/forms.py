import re
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from flask_login import current_user
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, TextAreaField
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
    password = PasswordField(
        'Password',
        validators=[DataRequired()]
    )
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('password')]
    )
    submit = SubmitField('Sign Up')
    role = None

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
    aws_access_key_id = StringField('AWS Access Key ID')
    aws_secret_access_key = PasswordField('AWS Secret Access Key')
    aws_session_token = TextAreaField('AWS Session Token')
    submit = SubmitField('Login')





