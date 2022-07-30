from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, ValidationError


class CheckAnswerForm(FlaskForm):
    task = IntegerField('tid')
    user = IntegerField('uid')
    answer = StringField('Ответ', validators=[DataRequired()])
    submit = SubmitField('Проверить ответ')


class SendPoemForm(FlaskForm):
    poem_text = TextAreaField('Ваше четверостишие', validators=[DataRequired()])
    send = SubmitField('Отправить')

    def validate_poem_text(self, poem_text):
        if len(poem_text.data.strip().split('\n')) != 4:
            print('Вызываем ошибку 4 строк')
            raise ValidationError('Четверостишие должно состоять из 4 строк')
