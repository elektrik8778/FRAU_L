from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, IntegerField
from wtforms.fields.html5 import TelField, EmailField
from wtforms.validators import DataRequired, EqualTo, ValidationError, Email
from app.models import User


class LoginForm(FlaskForm):
    login = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('ВОЙТИ')


class RegistrationForm(FlaskForm):
    # username = StringField('Логин', validators=[DataRequired()])
    first_name = StringField('Как тебя зовут? (Фамилия и Имя)', validators=[DataRequired()])
    # last_name = StringField('Фамилия')
    # email = EmailField('E-mail', validators=[DataRequired()])
    # phone = TelField('Телефон', validators=[DataRequired()])
    group = SelectField('Выбери свой часовой пояс', validators=[DataRequired()])
    # team = SelectField('Выбери свою команду')
    # password = PasswordField('Пароль', validators=[DataRequired()])
    # password2 = PasswordField('Повторите пароль', validators=[DataRequired(), EqualTo('password', message='Пароли не совпадают')])
    tg_id = StringField('TG id')
    # pesonal_data = BooleanField('Согласен на обработку персональных данных', validators=[DataRequired()])
    submit = SubmitField('ЗАРЕГИСТРИРОВАТЬСЯ')

    def validate_group(self, group):
        if int(group.data) == 0:
            raise ValidationError('Нужно обязательно выбрать свой часовой пояс')

    # def validate_username(self, username):
    #     no_spaces = username.data.replace(' ', '')
    #     if no_spaces == '':
    #         raise ValidationError('Имя пользователя не может состоять только из пробелов')
    #     user = User.query.filter_by(username=username.data).first()
    #     if user is not None:
    #         raise ValidationError('Пользователь с таким номером уже есть в системе, выберете другое.')

    # def validate_email(self, email):
    #     user = User.query.filter_by(email=email.data).first()
    #     if user is not None:
    #         raise ValidationError('Пользователь с такой почтой уже есть в системе.')

    # def validate_phone(self, phone):
    #     user = User.query.filter_by(phone=phone.data).first()
    #     if user is not None:
    #         raise ValidationError('Пользователь с таким номером телефона уже есть в системе.')


class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Ваш e-mail', validators=[DataRequired(), Email()])
    submit = SubmitField('Восстановить')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('Новый пароль', validators=[DataRequired()])
    password2 = PasswordField('Повторите новый пароль', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Сохранить')
