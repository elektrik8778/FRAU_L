from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, DateTimeField, IntegerField, TextAreaField, FileField, SelectField, \
    SelectMultipleField, MultipleFileField, BooleanField, FloatField
from wtforms.ext.sqlalchemy.fields import QuerySelectMultipleField, QuerySelectField
from wtforms.validators import DataRequired
from app.models import User, Group
from app import Config


class ChangeWebhookForm(FlaskForm):
    url = StringField('Webhook URL', validators=[DataRequired()])
    submit = SubmitField('Если не знаешь зачем эта кнопка - не нажимай, пожалуйста')


class ScheduledMessageCreateForm(FlaskForm):
    message_type = SelectField('Тип сообщения', choices=[('text', 'Текст'), ('photo', 'Фото'), ('video', 'Видео'), ('poll', 'Опрос')])
    date_time = DateTimeField('Дата и время отправки')
    text = TextAreaField('Текст сообщения')
    content_link = FileField('Ссылка на вложение')
    group = SelectField('Группа адрессатов')
    submit = SubmitField('Запланировать')


class SendTGMessageForm(FlaskForm):
    text = TextAreaField('Текст', validators=[DataRequired()])
    submit = SubmitField('Отправить')


class SendGroupTGMessageForm(FlaskForm):
    groups = SelectField('Группа', choices=[('всем', 'всем')])
    tags = SelectField('Атрибут', choices=[('всем', 'всем')])
    text = TextAreaField('Текст', validators=[DataRequired()])
    submit = SubmitField('Отправить')


class CreateGroupForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    submit = SubmitField('Добавить')


class CreateModerForm(FlaskForm):
    from app import create_app
    app = create_app(config_class=Config)
    with app.app_context():
        group = QuerySelectMultipleField('Группа',
                                         query_factory=Group.query.all,
                                         get_pk=lambda group: group.id,
                                         get_label=lambda group: group.name)
        user = QuerySelectField('Пользователь',
                                query_factory=User.query.filter(User.role == 'admin').all,
                                get_pk=lambda user: user.tg_id,
                                get_label=lambda user: user.first_name)
        submit = SubmitField('Добавить')


class CreateQuestionForm(FlaskForm):
    question_type = SelectField('Тип вопроса',
                                choices=[('text', 'text'), ('photo', 'photo'), ('video', 'video'), ('audio', 'audio')])
    question_text = TextAreaField('Текст вопроса', validators=[DataRequired()])
    variants = TextAreaField('Варианты ответов')
    question_content = MultipleFileField('Ссылка на вложение')
    answer_type = SelectField('Тип ответа',
                              choices=[('text', 'text'), ('photo', 'photo'), ('video', 'video'), ('audio', 'audio')])
    right_answer_text = TextAreaField('Текст верного ответа')
    wrong_answer_text = TextAreaField('Текст неверного ответа')
    answer_content = FileField('Ссылка на вложение')
    answer_explanation = TextAreaField('Пояснение')
    save_question = SubmitField('Сохранить')


class EditQuizForm(FlaskForm):
    quiz_name = StringField('Название викторины')
    quiz_description = TextAreaField('Сообщение перед началом')
    quiz_final_text = TextAreaField('Сообщение после окончания')
    command = StringField('Команда для запуска')
    save_quiz = SubmitField('Сохранить')


class SearchUserForm(FlaskForm):
    name = StringField('ФИО')
    search = SubmitField('Найти')


class FileUploadForm(FlaskForm):
    files = MultipleFileField('Файлы', validators=[DataRequired()])
    upload = SubmitField('Загрузить')


class TripForm(FlaskForm):
    # name = db.Column(db.String(128), nullable=False)
    # description = db.Column(db.String(1024))
    # status = db.Column(db.Boolean, default=False)
    # media = db.Column(db.JSON)
    # price = db.Column(db.Float, default='999')
    # payment_invite = db.Column(db.Text)
    # success_payment_text = db.Column(db.String(1024))
    # final_text = db.Column(db.String(1024))
    name = StringField('Название', validators=[DataRequired()])
    description = TextAreaField('Описание')
    status = BooleanField('Активна', default=False)
    media = MultipleFileField('Видюшки, картинки')
    price = FloatField('Цена', default='999')
    payment_invite = TextAreaField('Текст предложения оплатить')
    success_payment_text = TextAreaField('Текст при удачной оплате')
    final_text = TextAreaField('Текст в конце экскурсии')
    save = SubmitField('Сохранить')


class TripPointForm(FlaskForm):
    # name = db.Column(db.String(128), nullable=False)
    # description = db.Column(db.String(1024))
    # status = db.Column(db.Boolean, default=False)
    # order = db.Column(db.Integer)
    # media = db.Column(db.JSON)
    # meet_point_pic = db.Column(db.JSON)
    # location = db.Column(db.JSON)
    # voice = db.Column(db.JSON, default={"files": []})
    name = StringField('Название', validators=[DataRequired()])
    description = TextAreaField('Описание')
    status = BooleanField('Активна', default=False)
    order = IntegerField('Номер по порядку в экскурсии')
    media = MultipleFileField('Видюшки, картинки')
    meet_point_pic = MultipleFileField('Картинка места встречи')
    location = StringField('Координаты с Яндекс.Карт')
    voice = MultipleFileField('Голос')
    save = SubmitField('Сохранить')


class ChangeFileDescription(FlaskForm):
    filename = StringField('Имя файла')
    description = StringField('Описание')
    save = SubmitField('Сохранить')


class GetFileIDForm(FlaskForm):
    filename = StringField('Имя файла')
    filetype = StringField('Тип файла')
    file_id = StringField('file id')
    get_id = SubmitField('Получить')
