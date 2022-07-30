import json
import os
import threading
from datetime import datetime, timedelta
from app import db, bot
from app.admin import bp
from app.models import Food, FoodCategory, FoodOrder, FoodPhoto, Promocode, ScheduledMessage, User, Group, Quiz, Question, Tag, TaskForSending, UserTag
from app.admin.forms import ChangeWebhookForm, ScheduledMessageCreateForm, SendTGMessageForm, SendGroupTGMessageForm,\
    CreateGroupForm, CreateModerForm, CreateQuestionForm, EditQuizForm, FileUploadForm, TripForm, TripPointForm, \
    ChangeFileDescription, GetFileIDForm
from config import Config
from flask_login import login_required, current_user
from flask import render_template, redirect, url_for, request, flash, send_file, g
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from telegram import TelegramError, ParseMode
from telegram.error import BadRequest
from app.telegram_bot.handlers import greet_user, create_button_map, get_inline_menu
from app.telegram_bot.helpers import with_app_context
from sqlalchemy import over, func, cast, Text, desc
from flask_sqlalchemy import BaseQuery
import re
from pprint import pprint


@bp.route('/admin')
@login_required
def admin():
    if current_user.role == 'admin' or current_user.role == 'moderator':
        send_group_tg_mes_form = SendGroupTGMessageForm()
        return render_template('admin/admin.html',
                               send_group_tg_mes_form=send_group_tg_mes_form,
                               title='Админка')
    else:
        return redirect(url_for('main.index'))


@bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if current_user.role == 'admin' or current_user.role == 'moderator':
        webhook_form = ChangeWebhookForm()
        if webhook_form.validate_on_submit():
            try:
                bot.set_webhook(url=webhook_form.url.data)
                flash(f'Вебхук установлен на {webhook_form.url.data}')
            except(TelegramError):
                flash(f'Вебхук не установлен. Ошибка {str(TelegramError)}')
        webhook_form.url.data = url_for('telegram_bot.telegram', _external=True)
        return render_template('admin/admin_settings.html', title='Настройки', form=webhook_form)
    else:
        return redirect(url_for('main.index'))


@bp.route('/admin/message_schedule', methods=['GET', 'POST'])
@login_required
def message_schedule():
    if current_user.role == 'admin':
        create_task_form = ScheduledMessageCreateForm()
        create_task_form.group.choices = [('', 'выбрать группу')] + [(str(x.id), x.name) for x in Group.query.all()]
        scheduled_messages = ScheduledMessage.query.order_by(ScheduledMessage.date_time).all()
        if create_task_form.validate_on_submit():
            task = ScheduledMessage()
            task.message_type = create_task_form.message_type.data
            task.date_time = create_task_form.date_time.data
            task.text = create_task_form.text.data
            if create_task_form.group.data:
                task.group = int(create_task_form.group.data)
            if task.message_type != 'text' and task.message_type != 'poll':
                f = create_task_form.content_link.data
                filename = f.filename
                if not os.path.exists(os.path.join(Config.UPLOAD_FOLDER, 'bulk_messages')):
                    os.makedirs(os.path.join(Config.UPLOAD_FOLDER, 'bulk_messages'))
                f.save(os.path.join(Config.UPLOAD_FOLDER, 'bulk_messages', filename))
                task.content_link = os.path.join(Config.UPLOAD_FOLDER, 'bulk_messages', filename)
            else:
                task.content_link = ''
            db.session.add(task)
            db.session.commit()
            if task.content_link:
                with open(task.content_link, 'rb') as file_to_send:
                    if task.message_type == 'photo':
                        response = bot.send_photo(chat_id=current_user.tg_id,
                                                  photo=file_to_send)
                        bot.delete_message(response.chat.id, response.message_id)
                        task.content_link = response.photo[-1].file_id
                        db.session.commit()
                    if task.message_type == 'video':
                        # вычисляем размер видео
                        import cv2
                        file_path = task.content_link
                        vid = cv2.VideoCapture(file_path)
                        height = vid.get(cv2.CAP_PROP_FRAME_HEIGHT)
                        width = vid.get(cv2.CAP_PROP_FRAME_WIDTH)

                        response = bot.send_video(chat_id=current_user.tg_id,
                                                  video=file_to_send,
                                                  width=width,
                                                  height=height)

                        bot.delete_message(response.chat.id, response.message_id)
                        task.content_link = response.video.file_id
                        db.session.commit()
            return redirect(url_for('admin.message_schedule'))

        return render_template('admin/message_schedule.html',
                               title='Предустановленные сообщения',
                               form=create_task_form,
                               scheduled_messages=scheduled_messages)


    else:
        return redirect(url_for('main.index'))


@bp.route('/admin/message_schedule/delete_<id>', methods=['GET', 'POST'])
@login_required
def delete_task(id):
    task = ScheduledMessage.query.get(int(id))

    # удаляем из запланированных к отправке заданий
    TaskForSending.query.filter(TaskForSending.scheduled_message_id == task.id).delete()

    # удаляем само сообщение
    db.session.delete(task)
    db.session.commit()
    return redirect(request.referrer)


@bp.route('/admin/message_schedule/del_sent_messages/<schedule_message_id>')
@login_required
def del_sent_messages(schedule_message_id):
    sm: ScheduledMessage = ScheduledMessage.query.get(int(schedule_message_id))
    tasks = sm.get_tasks_for_sending(sent=True, deleted=False)
    # Удаление отправленных в фоне
    thr = threading.Thread(target=del_tasks, args=[tasks, db])
    thr.start()
    return redirect(request.referrer)


def set_task_deleted(t):
    t.deleted = True
    t.deleted_time = datetime.now()
    db.session.merge(t)
    db.session.commit()


@with_app_context
def del_tasks(tasks, db):
    for t in tasks:
        if (datetime.now() - t.fact_sending_time).total_seconds() < 172800 and t.message_id:
            try:
                response = bot.delete_message(chat_id=t.get_user().tg_id, message_id=t.message_id)
                set_task_deleted(t)
            except BadRequest:
                print(f'Сообщение {t.message_id} не найдено')
                set_task_deleted(t)


@bp.route('/admin/user/<id>', methods=['GET', 'POST'])
@login_required
def user_detailed(id):
    send_tg_mes_form = SendTGMessageForm()
    user = User.query.filter_by(id=int(id)).first()
    received_scheduled_messages = TaskForSending.query.filter(TaskForSending.user_id == id).order_by(TaskForSending.fact_sending_time).all()
    # numbers: LotteryNumber = LotteryNumber.query.filter(LotteryNumber.user_id == id).order_by(LotteryNumber.res_date).all()
    tags = Tag.query.all()

    if send_tg_mes_form.validate_on_submit():
        if send_tg_mes_form.submit.data and send_tg_mes_form.validate():
            text = send_tg_mes_form.text.data
            bot.send_message(chat_id=user.tg_id, text=text, parse_mode='Markdown')
            return redirect(url_for('admin.user_detailed', id=user.id))
    return render_template('admin/user_detailed.html',
                           user=user,
                           send_tg_mes_form=send_tg_mes_form,
                           # numbers=numbers,
                           messages=received_scheduled_messages,
                           title=f'Пользователь {user.first_name}',
                           now=datetime.now())


@bp.route('/admin/users_list', methods=['GET', 'POST'])
@login_required
def users_list():
    tags = Tag.query.all()
    return render_template('admin/users_all.html', tags=json.dumps([(str(tag.id), str(tag.name)) for tag in tags], ensure_ascii=False))


@bp.get('/admin/get_users_data')
@bp.post('/admin/get_users_data')
@login_required
def get_users_data():
    query: BaseQuery = db.session.query(User.id, User.tg_id, User.first_name, User.status, User.role, User.phone, Group.name.label('group'),
                             over(func.string_agg(cast(Tag.id, Text)+'_'+Tag.name, '\n'),
                                  partition_by=User.id).label('tags'),
                             # over(func.string_agg(cast(ScheduledMessage.id, Text), ', '),
                             #      partition_by=User.id).label('messages'),
                             # func.count(TicketUser.id).label('tickets')
                             ).distinct()\
        .join(Group, Group.id == User.group) \
        .join(UserTag, User.id == UserTag.user_id, full=True)\
        .join(Tag, Tag.id == UserTag.tag_id, isouter=True)\
        .group_by(User.id, Group.name, Tag.id)

    # .join(TicketUser, TicketUser.user_id == User.id, full=True) \

    # print(query)
    # print(query.all()[0].keys())

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            User.status.like(f'%{search}%'),
            User.first_name.like(f'%{search}%'),
            User.phone.like(f'%{search}%'),
            Group.name.like(f'%{search}%'),
            Tag.name.like(f'%{search}%')
        ))
    total_filtered = query.count()

    # sorting
    order = []
    i = 0
    while True:
        col_index = request.args.get(f'order[{i}][column]')
        if col_index is None:
            break
        col_name = request.args.get(f'columns[{col_index}][data]')
        if col_name == 'tickets':
            descending = request.args.get(f'order[{i}][dir]') == 'desc'
            if descending:
                order.append(desc('tickets'))
            else:
                order.append('tickets')
        if col_name not in ['id', 'first_name']:
            col_name = 'id'
        descending = request.args.get(f'order[{i}][dir]') == 'desc'
        col = getattr(User, col_name)

        if descending:
            col = col.desc()
        order.append(col)
        i += 1
    if order:
        query = query.order_by(*order)

    # pagination
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = query.offset(start).limit(length)

    def to_dict(row, index):
        return {
            'num': index + 1,
            'id': row.id,
            'first_name': row.first_name,
            'tg_id': row.tg_id,
            'group': row.group,
            'status': row.status,
            'tags': row.tags,
            'phone': row.phone,
            'role': row.role,
            # 'messages': row.messages,
            # 'tickets': row.tickets
        }

    # response
    return {
        'data': [to_dict(user, index) for index, user in enumerate(query)],
        'recordsFiltered': total_filtered,
        'recordsTotal': len(User.query.all()),
        'draw': request.args.get('draw', type=int),
    }


@bp.get('/admin/get_user_tags/<user_id>')
def get_user_tags(user_id):
    return json.dumps([(str(tag.id), str(tag.name)) for tag in User.query.get(int(user_id)).get_tags()], ensure_ascii=False)


@bp.route("/admin/categories")
def categories():
    g.categories = FoodCategory.query.order_by('id').all()
    g.food = Food
    return render_template('admin/categories.html')


@bp.route("/admin/bfood/add")
@bp.route("/admin/bfood/edit/<fid>")
def b_foods(fid=None):
    if fid is not None:
        g.fid = fid
    return render_template("admin/item_form.j2")


@bp.route("/admin/orders")
def orders():
    return render_template('admin/orders.html',
                           orders=FoodOrder.query.order_by(desc(FoodOrder.id)).all())


@bp.get('/admin/promocodes')
def promocodes():
    g.promocodes = Promocode.query.all()
    return render_template('admin/promocodes.html')


@bp.post('/admin/promocodes')
def make_promo():
    promo = Promocode()
    promo.code = request.form.get('code')
    promo.discount = request.form.get('discount')
    promo.name = request.form.get('name')
    promo.enabled = (request.form.get('enabled') == 'on')
    promo.desc = request.form.get('desc') or request.form.get('name')
    db.session.add(promo)
    db.session.commit()
    return redirect(url_for('admin.promocodes'))


@bp.route("/admin/foods")
def foods():
    form = FileUploadForm()
    if cat := request.args.get('cat'):
        foods = Food.query.filter_by(category=cat).order_by('id').all()
    else:
        foods = Food.query.order_by('id').all()
    g.foods = foods
    g.pics = FoodPhoto
    g.cat = FoodCategory
    return render_template("admin/foods.html",
                           form=form)


@bp.route('/admin/food/edit/<id>')
def edit_food(id):
    g.food = Food.query.get(id)
    g.cat = FoodCategory
    g.photos = FoodPhoto.query.filter_by(belongs_to=g.food.id)
    return render_template('admin/_item_dialogue.html')


@bp.get('/admin/files')
def files():
    form = FileUploadForm()
    files_dir = os.path.join(Config.UPLOAD_FOLDER, 'files')
    if not os.path.exists(files_dir):
        os.makedirs(files_dir)
    files = os.listdir(files_dir)
    return render_template('admin/my_files.html',
                           files=files,
                           s=os.environ.get('TG_ADDR'),
                           form=form)


@bp.post('/admin/files')
def files_upload():
    # from werkzeug.datastructures import ImmutableMultiDict
    form = FileUploadForm()
    files_dir = os.path.join(Config.UPLOAD_FOLDER, 'files')
    if not os.path.exists(files_dir):
        os.makedirs(files_dir)

    if form.validate_on_submit():
        for f in request.files.getlist('files'):
            if 'image' in f.content_type:
                f.save(os.path.join(files_dir, f.filename))
                response = bot.send_photo(chat_id=current_user.tg_id,
                                          photo=f'https://{os.environ.get("TG_ADDR")}/get_file/{f.filename}')
                bot.delete_message(chat_id=current_user.tg_id,
                                   message_id=response.message_id)
                os.rename(os.path.join(files_dir, f.filename), os.path.join(files_dir, f'{response.photo[-1].file_id}_{f.filename}'))
                # bot.send_message(chat_id=current_user.tg_id,
                #                  text=f'[файл](https://{os.environ.get("TG_ADDR")}/get_file/{f.filename})',
                #                  parse_mode=ParseMode.MARKDOWN)

    return redirect(request.referrer)


@bp.get('/get_file/<filename>')
def get_file(filename):
    files_dir = os.path.join(Config.UPLOAD_FOLDER, 'files')
    if not os.path.exists(files_dir):
        os.makedirs(files_dir)

    if os.path.exists(os.path.join(files_dir, filename)):
        return send_file(path_or_file=os.path.join(files_dir, filename))


@bp.get('/del_file/<filename>')
def del_file(filename):
    files_dir = os.path.join(Config.UPLOAD_FOLDER, 'files')
    os.remove(os.path.join(files_dir, filename))
    return redirect(request.referrer)


@bp.post('/admin/set_user_tag')
def set_user_tag():
    data = json.loads(request.get_data())
    return User.query.get(int(data['uid'])).add_tag(Tag.query.get(int(data['tid'])))


@bp.post('/admin/del_user_tag')
def del_user_tag():
    data = json.loads(request.get_data())
    return User.query.get(int(data['uid'])).del_tag(Tag.query.get(int(data['tid'])))


@bp.route('/admin/send_menu/<user_id>', methods=['GET', 'POST'])
@login_required
def admin_send_menu(user_id):
    user: User = User.query.get(user_id)
    if user.tg_id:
        greet_user(user)
    return redirect(request.referrer)


@bp.route('/admin/set_empty_status/<user_id>')
@login_required
def set_empty_status(user_id):
    User.query.get(user_id).status = ''
    db.session.commit()
    return redirect(request.referrer)


@bp.route('/admin/user_view_settings', methods=['GET', 'POST'])
@login_required
def user_view_settings():
    if current_user.role == 'admin' or current_user.role == 'moderator':
        return render_template('admin/user_view_settings.html', title='Настройки внешнего вида платформы')
    else:
        return redirect(url_for('main.index'))


@bp.route('/test_send_task_<id>')
def test_send_task(id):
    task = ScheduledMessage.query.get(id)
    text = task.text
    if task.message_type == 'photo':
        bot.send_photo(chat_id=current_user.tg_id,
                                  photo=task.content_link,
                                  caption=text,
                                  parse_mode=ParseMode.MARKDOWN)
    elif task.message_type == 'text':
        bot.send_message(chat_id=current_user.tg_id,
                         text=text,
                         parse_mode=ParseMode.MARKDOWN,
                         disable_web_page_preview=False)
    elif task.message_type == 'video':
        bot.send_video(chat_id=current_user.tg_id,
                       video=task.content_link,
                       caption=text,
                       parse_mode=ParseMode.MARKDOWN)
    elif task.message_type == 'poll':
        send_quiz_start(quiz_id=int(text), users=[current_user])
    return redirect(url_for('admin.message_schedule'))


@bp.route('/moderation', methods=['GET', 'POST'])
@login_required
def moderation():
    if current_user.role == 'admin':
        groups = Group.query.all()
        admins = User.query.filter_by(role='admin').all()

        current_time = {}

        create_moderator_form = CreateModerForm()
        for group in groups:
            current_time[group.name] = datetime.now() + timedelta(hours=int(group.time_zone)) - timedelta(hours=int(Config.SERVER_TIME_ZONE))

        if create_moderator_form.validate_on_submit():
            if create_moderator_form.submit.data and create_moderator_form.validate():
                for group in create_moderator_form.group.data:
                    gr = Group.query.get(group.id)
                    us = User.query.get(create_moderator_form.user.data.id)
                    gr.moderators.append(us)
                    db.session.commit()
                return redirect(request.referrer)

        create_group_form = CreateGroupForm()
        if create_group_form.validate_on_submit():
            if create_group_form.submit.data and create_group_form.validate():
                group = Group()
                group.name = create_group_form.name.data
                db.session.add(group)
                db.session.commit()
                return redirect(request.referrer)

        return render_template('admin/moderation.html', groups=groups, create_group_form=create_group_form,
                               create_moderator_form=create_moderator_form, current_time=current_time)
    else:
        return redirect(url_for('main.index'))


@bp.route('/del_moderator_<group_id>_<user_id>', methods=['GET', 'POST'])
@login_required
def del_moderator(group_id, user_id):
    group = Group.query.get(group_id)
    user = User.query.get(user_id)
    group.moderators.remove(user)
    db.session.commit()
    return redirect(url_for('admin.moderation'))


@bp.route('/del_user_<user_id>', methods=['GET', 'POST'])
@login_required
def del_user(user_id):
    user = User.query.get(user_id)
    messages = user.all_messages()
    groups = Group.query.all()
    tags = user.tags
    for message in messages:
        # for chat_message in chat_messages:
        #     if message.id == chat_message.message_id:
        #         db.session.delete(chat_message)
        db.session.delete(message)
    for group in groups:
        if user in group.moderators:
            group.moderators.remove(user)
    for tag in tags:
        user.tags.remove(tag)
    for invited in user.his_invited_users:
        user.his_invited_users.remove(invited)
    # for card in lotocards:
    #     db.session.delete(card)
    db.session.commit()
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin.users_list'))


@bp.route('/set_role_<user_id>', methods=['GET', 'POST'])
@login_required
def set_user_role(user_id):
    user = User.query.get(user_id)
    if user.role == 'admin':
        regions = Group.query.all()
        for region in regions:
            if user in region.moderators:
                region.moderators.remove(user)
        user.role = ''
    else:
        user.role = 'admin'
    db.session.commit()
    return redirect(url_for('admin.users_list'))


@bp.route('/del_group_<group_id>', methods=['GET', 'POST'])
@login_required
def del_group(group_id):
    group = Group.query.get(group_id)
    users = User.query.all()
    for user in users:
        if user.group == group.id:
            user.group = f'{group.name}_удален'
    for moderator in group.moderators:
        group.moderators.remove(moderator)
    db.session.delete(group)
    db.session.commit()
    return redirect(url_for('admin.moderation'))


@bp.route('/quiz_list', methods=['GET', 'POST'])
@login_required
def quiz_list():
    quizes = Quiz.query.all()
    create_question_form = CreateQuestionForm()
    if create_question_form.validate_on_submit():
        print('Создаем вопрос')
    return render_template('admin/quiz_list.html', quizes=quizes, create_question_form=create_question_form)


@bp.route('/create_quiz_<quiz_id>', methods=['GET', 'POST'])
@login_required
def create_quiz(quiz_id):
    if quiz_id == 'new':
        quiz = Quiz()
        quiz.name = f'Новая_{len(Quiz.query.all())+1}'
        db.session.add(quiz)
        db.session.commit()
        return redirect(url_for('admin.create_quiz', quiz_id=quiz.id))
    else:
        quiz = Quiz.query.get(quiz_id)
        create_question_form = CreateQuestionForm()
        edit_quiz_form = EditQuizForm()

        if edit_quiz_form.validate_on_submit() and edit_quiz_form.save_quiz.data:

            quiz.name = edit_quiz_form.quiz_name.data

            if not edit_quiz_form.quiz_description.data:
                quiz.description = None
            else:
                quiz.description = edit_quiz_form.quiz_description.data

            if edit_quiz_form.quiz_final_text.data == '':
                quiz.final_text = None
            else:
                quiz.final_text = edit_quiz_form.quiz_final_text.data

            if edit_quiz_form.command == '':
                quiz.command = None
            else:
                quiz.command = edit_quiz_form.command.data

            db.session.commit()
            return redirect(url_for('admin.create_quiz', quiz_id=quiz.id))

        if create_question_form.validate_on_submit() and create_question_form.save_question.data:
            save_question(request, create_question_form, quiz)
            return redirect(url_for('admin.create_quiz', quiz_id=quiz.id, edit_quiz_form=edit_quiz_form))

        if quiz.description:
            edit_quiz_form.quiz_description.data = quiz.description
        if quiz.final_text:
            edit_quiz_form.quiz_final_text.data = quiz.final_text
        if quiz.command:
            edit_quiz_form.command.data = quiz.command

        return render_template('admin/create_quiz.html',
                               quiz=quiz,
                               create_question_form=create_question_form,
                               edit_quiz_form=edit_quiz_form)


def save_question(request, create_question_form, quiz, question=None):
    quiz_files_catalog = f'app/static/uploads/quiz/{quiz.id}'
    variants = ''
    form = request.form
    for i in form:
        if re.match('variant-\d+', i):
            right = ''
            if f'right-{i.split("-")[-1]}' in form:
                right = '(верный)'
            if right:
                variants += f'{form[i]} {right}\n'
            else:
                variants += f'{form[i]}\n'

    if not question:
        question = Question()
    question.quiz_id = quiz.id
    question.question_type = create_question_form.question_type.data
    question.question_text = create_question_form.question_text.data
    question.question_variants = variants.strip()

    if question.question_type != 'text':
        # проверили, что есть каталог или создали
        if not os.path.exists(quiz_files_catalog):
            os.makedirs(quiz_files_catalog)
        files = create_question_form.question_content.data

        # если в форме есть файлы для вопроса
        if files[0].filename != '':
            # удалить старые файлы физически
            if question.question_content_link:
                for old_file in question.question_content_link.split(','):
                    os.remove(old_file)
            # удалить ссылки на старые файлы из базы
            question.question_content_link = ''
            question.question_content = ''

            # добавить новые файлы
            for f in files:
                filename = f.filename
                f.save(os.path.join(quiz_files_catalog, filename))
                if not question.question_content_link:
                    question.question_content_link = f'{os.path.join(quiz_files_catalog, filename)}'
                else:
                    question.question_content_link += f',{os.path.join(quiz_files_catalog, filename)}'

            if question.question_type == 'photo':
                for link in question.question_content_link.split(','):
                    with open(link, 'rb') as photo:
                        response = bot.send_photo(chat_id=current_user.tg_id,
                                                  photo=photo,
                                                  caption=f'Викторина {quiz.id}, вопрос {question.question_text}')
                        if not question.question_content:
                            question.question_content = f'{response.photo[-1].file_id}'
                        else:
                            question.question_content += f',{response.photo[-1].file_id}'
                        bot.delete_message(chat_id=current_user.tg_id,
                                           message_id=response.message_id)
            elif question.question_type == 'video':
                with open(question.question_content_link, 'rb') as video:
                    response = bot.send_video(chat_id=current_user.tg_id,
                                              video=video,
                                              caption=f'Викторина {quiz.id}, вопрос {question.question_text}')
                    question.question_content = response.video.file_id
                    bot.delete_message(chat_id=current_user.tg_id,
                                       message_id=response.message_id)
            elif question.question_type == 'audio':
                with open(question.question_content_link, 'rb') as audio:
                    response = bot.send_audio(chat_id=current_user.tg_id,
                                              audio=audio,
                                              caption=f'Викторина {quiz.id}, вопрос {question.question_text}')
                    question.question_content = response.audio.file_id
                    bot.delete_message(chat_id=current_user.tg_id,
                                       message_id=response.message_id)
    else:
        question.question_content_link = ''
        question.question_content = ''

    question.answer_type = create_question_form.answer_type.data
    question.right_answer_text = create_question_form.right_answer_text.data
    question.wrong_answer_text = create_question_form.wrong_answer_text.data
    question.answer_explanation = create_question_form.answer_explanation.data

    if question.answer_type != 'text':
        if not os.path.exists(quiz_files_catalog):
            os.makedirs(quiz_files_catalog)
        f = create_question_form.answer_content.data
        if f.filename:
            # удалить старые фото
            if question.answer_content_link:
                os.remove(question.answer_content_link)
            # сохранить новые
            filename = f.filename
            f.save(os.path.join(quiz_files_catalog, filename))
            question.answer_content_link = os.path.join(quiz_files_catalog, filename)
            if question.answer_type == 'photo':
                with open(question.answer_content_link, 'rb') as photo:
                    response = bot.send_photo(chat_id=current_user.tg_id,
                                              photo=photo,
                                              caption=f'Викторина {quiz.id}, ответ {question.answer_text}')
                    question.answer_content = response.photo[-1].file_id
                    bot.delete_message(chat_id=current_user.tg_id,
                                       message_id=response.message_id)
            elif question.answer_type == 'video':
                with open(question.answer_content_link, 'rb') as video:
                    response = bot.send_video(chat_id=current_user.tg_id,
                                              video=video,
                                              caption=f'Викторина {quiz.id}, ответ {question.answer_text}')
                    question.answer_content = response.video.file_id
                    bot.delete_message(chat_id=current_user.tg_id,
                                       message_id=response.message_id)
            elif question.answer_type == 'audio':
                with open(question.answer_content_link, 'rb') as audio:
                    response = bot.send_audio(chat_id=current_user.tg_id,
                                              audio=audio,
                                              caption=f'Викторина {quiz.id}, ответ {question.answer_text}')
                    question.answer_content = response.audio.file_id
                    bot.delete_message(chat_id=current_user.tg_id,
                                       message_id=response.message_id)
    else:
        question.answer_content = ''
        question.answer_content_link = ''
    db.session.add(question)
    # quiz.questions.append(question)
    db.session.commit()


@bp.get('/admin/question/<qid>')
def question_datailed(qid):
    q: Question = Question.query.get(int(qid))

    variants = {}
    variants_list = q.question_variants.split('\n')
    for index, var in enumerate(variants_list):
        variants[index] = {
            'text': var.split('(верный)')[0].strip(),
            'right': True if '(верный)' in var else False
        }

    q_form = CreateQuestionForm()
    q_form.question_type.data = q.question_type
    q_form.question_text.data = q.question_text
    q_form.answer_type.data = q.answer_type
    q_form.right_answer_text.data = q.right_answer_text
    q_form.wrong_answer_text.data = q.wrong_answer_text
    q_form.answer_explanation.data = q.answer_explanation

    return render_template('/admin/question_detailed.html',
                           q=q,
                           form=q_form,
                           variants=json.dumps(variants, ensure_ascii=False))


@bp.post('/admin/question/<qid>')
def question_datailed_post(qid):
    q: Question = Question.query.get(int(qid))
    q_form = CreateQuestionForm()
    if q_form.validate_on_submit():
        save_question(request, q_form, q.quiz(), q)
        return redirect(request.referrer)


@bp.route('/send_quiz_<quiz_id>_<user_id>', methods=['GET', 'POST'])
@login_required
def send_quiz(quiz_id, user_id):
    user = User.query.get(user_id)
    send_quiz_start(quiz_id, [user])
    return redirect(url_for('admin.create_quiz', quiz_id=quiz_id))


@bp.route('/del_question_<quiz_id>_<question_id>', methods=['GET', 'POST'])
@login_required
def del_question(quiz_id, question_id):
    question = Question.query.get(question_id)
    if question.question_content_link and os.path.exists(question.question_content_link):
        os.remove(question.question_content_link)
    if question.answer_content_link and os.path.exists(question.answer_content_link):
        os.remove(question.answer_content_link)
    db.session.delete(question)
    db.session.commit()
    return redirect(url_for('admin.create_quiz', quiz_id=quiz_id))


@bp.route('/del_quiz_<quiz_id>', methods=['GET', 'POST'])
@login_required
def del_quiz(quiz_id):
    quiz = Quiz.query.get(quiz_id)
    for question in quiz.questions():
        if question.question_content_link and os.path.exists(question.question_content_link):
            os.remove(question.question_content_link)
        if question.answer_content_link and os.path.exists(question.answer_content_link):
            os.remove(question.answer_content_link)
        db.session.delete(question)
    db.session.commit()
    db.session.delete(quiz)
    db.session.commit()
    return redirect(url_for('admin.quiz_list'))


@bp.post('/admin/save_user_phone')
def save_user_phone():
    data = json.loads(request.get_data())
    user: User = User.query.get(int(data['uid']))
    user.phone = data['phone']
    db.session.commit()
    return 'ok'


def send_quiz_start(quiz_id, users):
    quiz = Quiz.query.get(quiz_id)
    buttons = [
        {
            'text': 'Начинаем',
            'data': f'startQuiz_{quiz_id}'
        }
    ]
    map = create_button_map(buttons, 1)
    reply_markup = get_inline_menu(map)
    for user in users:
        bot.send_message(chat_id=user.tg_id,
                         text=quiz.description,
                         reply_markup=reply_markup,
                         parse_mode='Markdown')
        user.status = f'playQuiz_{quiz.id}_0'
        db.session.commit()
        return 'ok'
