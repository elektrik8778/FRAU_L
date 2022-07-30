from urllib import request
from app.telegram_bot.helpers import with_app_context
from app import db, bot
from app.models import User, Quiz, Question, UserQuestion, Group, FoodOrder, UserBonus
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, InputMediaAudio, LabeledPrice, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from app.telegram_bot import texts
from app import Config
from telegram import Update, ParseMode, Poll
import os
from datetime import datetime
import json
import math
import requests
import cv2
from google.cloud import dialogflow_v2 as dialogflow
from google.cloud.dialogflow_v2 import DetectIntentResponse
from googleapiclient.discovery import build
from google.oauth2 import service_account
import re

def greet_user(user: User):
    photo = None
    try:
        with open('app/static/images/logo.fid', 'r') as fid:
            photo = fid.read()
    except Exception as e:
        print(e)
        photo = open('app/static/images/logo.jpg', 'rb')

    response = bot.send_photo(chat_id=user.tg_id,
                              caption=f"{texts.greeting(user)}",
                              photo=photo,
                              parse_mode=ParseMode.MARKDOWN,
                              reply_markup=ReplyKeyboardRemove()
                              )
    if not isinstance(photo, str):
        photo.close()
    with open('app/static/images/logo.fid', 'w') as fid:
        fid.write(response.photo[-1].file_id)


    try:
        with open('app/static/images/bot_images/menu_hint.fid', 'r') as fid:
            photo = fid.read()
    except Exception as e:
        print(e)
        photo = open('app/static/images/bot_images/menu_hint.png', 'rb')

    response = bot.send_photo(chat_id=user.tg_id,
                              caption="Подсказка",
                              photo=photo,
                              parse_mode=ParseMode.MARKDOWN,
                              reply_markup=ReplyKeyboardRemove()
                              )
    if not isinstance(photo, str):
        photo.close()
    with open('app/static/images/bot_images/menu_hint.fid', 'w') as fid:
        fid.write(response.photo[-1].file_id)

    return


def success_registration(user: User):
    # отправляем сообщение об успехе
    photo = None
    vid = height = width = None
    try:
        with open('app/static/video/success_reg.fid', 'r') as fid:
            video = fid.read()
    except Exception as e:
        print(e)
        video = open('app/static/video/success_reg.mp4', 'rb')
        vid = cv2.VideoCapture('app/static/video/success_reg.mp4')
        height = vid.get(cv2.CAP_PROP_FRAME_HEIGHT)
        width = vid.get(cv2.CAP_PROP_FRAME_WIDTH)

    response = bot.send_video(chat_id=user.tg_id,
                              caption=f"{texts.success_registration(user)}",
                              video=video,
                              height=height,
                              width=width,
                              protect_content=True,
                              parse_mode=ParseMode.MARKDOWN)

    if not isinstance(video, str):
        video.close()
    with open('app/static/video/success_reg.fid', 'w') as fid:
        fid.write(response.video.file_id)

    response = bot.send_message(chat_id=user.tg_id,
                                text=f"А вот вам *бонусный первый* лотерейный билетик\n\n"
                                     f"Все свои лотерейки можно посмотреть в меню  *'Мои лотерейки'*",
                                parse_mode=ParseMode.MARKDOWN)

    if len(user.get_lottery_numbers()) == 0:
        user.create_lottery_number(reason='success_reg', description='первый бонусный').send(user)

    # получаем список билетов данного пользователя
    # если билетов у такого пользователя нет, даем бонусный
    # if not user.get_lottery_cards():
    #     for c in user.add_lottery_cards(count=1):
    #         bot.send_photo(chat_id=user.tg_id,
    #                        photo=f'{c.text}/{Config.LOTTO_API_TOKEN}')


@with_app_context
def command_start(update, context):
    # update.effective_message.delete()
    chat_id = update.effective_user.id
    btn = KeyboardButton(text="Отправить телефон", callback_data="start_phone", request_contact=True)
    user = User.query.filter_by(tg_id=chat_id).first()
    users_count = len(User.query.all())
    if not user:
        user = User()
        user.tg_id = chat_id
        user.status = 'wait_for_phone'
        user.set_password(str(chat_id))
        user.group = Group.query.first().id
        if users_count == 0:
            user.role = 'admin'
        else:
            user.role = 'user'
        try:
            user.first_name = update.message.from_user.first_name
        except:
            pass
        db.session.add(user)
        db.session.commit()
        # user.write_to_google_sheet()

        update.effective_chat.send_message(text="Для начала пользования ботом, поделитесь с нами номером телефона.\n\nДля этого:\n\nИЛИ нажмите кнопку *'Отправить телефон'* внизу\n\nИЛИ пришлите номер текстом  *в формате 89112223344*",
                                           reply_markup=ReplyKeyboardMarkup([[btn]], resize_keyboard=True),
                                           parse_mode=ParseMode.MARKDOWN)

        # return greet_user(user)
    else:
        if user.phone:
            user.status = ''
            db.session.commit()
            user.set_subscribed()
            greet_user(user)
        else:
            update.effective_chat.send_message(text="Для начала пользования ботом, поделитесь с нами номером телефона.\n\nДля этого:\n\nИЛИ нажмите кнопку *'Отправить телефон'* внизу\n\nИЛИ пришлите номер текстом  *в формате 89112223344*",
                                               reply_markup=ReplyKeyboardMarkup([[btn]], resize_keyboard=True),
                                               parse_mode=ParseMode.MARKDOWN)


@with_app_context
def set_order_paid(update: Update, context):
    order: FoodOrder = FoodOrder.query.get(int(update.callback_query.data.split('_')[-1]))
    order.set_paid()
    return 'ok'


@with_app_context
def cancel_order(update: Update, context):
    try:
        FoodOrder.query.get(int(update.callback_query.data.split('_')[-1])).cancel()
    except Exception as e:
        update.effective_message.reply_text(str(e))
    return 'ok'


@with_app_context
def command_bonus(update: Update, context):
    user: User = User.query.filter(User.tg_id == update.effective_user.id).first()
    bonus = user.get_users_bonuses_amount()
    update.effective_message.reply_text(f'У вас *{bonus}* бонусов', parse_mode=ParseMode.MARKDOWN)


@with_app_context
def command_help(update: Update, context):
    chat_id = int(update.message.from_user.id)
    message_id = int(update.message.message_id)
    sender: User = User.query.filter(User.tg_id == chat_id).first()
    update.message.delete()

    confirm_btn = InlineKeyboardButton(text='Да, помощь нужна', callback_data='help')
    cancel_btn = InlineKeyboardButton(text='Нет, помощь не нужна', callback_data='deleteMessage')

    keyboard = [[confirm_btn], [cancel_btn]]

    update.message.reply_text(
        text='🆘 Вы нажали кнопку помощи 🆘.\n\nЗачастую её нажимают просто так. А обработка каждого запроса требует времени помощников Дедушки Мороза.\n\n*Вам действительно нужна наша помощь?*',
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN)


@with_app_context
def help(update: Update, context):
    user = User.query.filter(User.tg_id == update.callback_query.from_user.id).first()
    update.callback_query.delete_message()
    texts.help(user)


@with_app_context
def delete_message(update: Update, context):
    update.callback_query.delete_message()


@with_app_context
def command_test(update: Update, context):
    command = update.message.text.split('/test')[-1].strip()
    quiz: Quiz = Quiz.query.filter(Quiz.command == command).first()
    user = User.query.filter(User.tg_id == update.message.from_user.id).first()

    if quiz:
        from app.admin.routes import send_quiz_start
        send_quiz_start(quiz.id, [user])


# старые
def command_users_count(update: Update, context):
    from app import create_app
    app = create_app(config_class=Config)
    app.app_context().push()

    all_users = User.query.all()
    tg_users = User.query.filter(User.tg_id.isnot(None)).all()
    unsubscribed_users = User.query.filter(User.tg_id.isnot(None), User.unsubscribed.is_(True)).all()
    user = User.query.filter_by(tg_id=update.message.from_user.id).first()
    bot.send_message(chat_id=user.tg_id,
                     text=f'*Всего в системе* {len(all_users)}\n'
                          f'*Бота подключили* {len(tg_users)}\n'
                          f'*Отписались* {len(unsubscribed_users)}',
                     parse_mode=ParseMode.MARKDOWN)


@with_app_context
def text_message(update, context):
    sender = User.query.filter_by(tg_id=update.message.from_user.id).first()
    text = update.message.text
    if sender.status == 'wait_for_phone':
        try:
            pattern = re.compile('^((8|\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{11,16}$')
            if re.match(pattern=pattern, string=text):
                sender.phone = text
                sender.status = ''
                db.session.commit()
                greet_user(sender)
                return
            else:
                raise 'WrongPhoneNumber'
        except:
            btn = KeyboardButton(text="Отправить телефон",
                                 callback_data="start_phone",
                                 request_contact=True,
                                 one_time_keyboard=True)
            update.effective_chat.send_message(
                text="Что-то пошло не так. Возможно, вы прислали номер телефона в неверном формате.\n\nДля начала пользования ботом, поделитесь с нами номером телефона. Для этого:\n\nИЛИ нажмите кнопку *'Отправить телефон'* внизу\n\nИЛИ пришлите номер текстом  *в формате 89112223344*",
                reply_markup=ReplyKeyboardMarkup([[btn]], resize_keyboard=True),
                parse_mode=ParseMode.MARKDOWN)
            return

    moderators = sender.get_group().moderators
    for user in moderators:
        response = bot.send_message(chat_id=user.tg_id,
                                    text=f'{texts.tg_user_mention(sender)}:\n\n{text}',
                                    parse_mode=ParseMode.MARKDOWN)
    return 'ok'


@with_app_context
def reply_message(update, context):
    sender_tg_id = None
    if c := update.message.contact:
        u = User.query.filter_by(tg_id=c.user_id).first()
        u.phone = c.phone_number
        db.session.merge(u)
        db.session.commit()
        greet_user(u)
        return
    if update.message.reply_to_message.entities:
        entities = update.message.reply_to_message.entities
        for entity in entities:
            if entity.type == 'text_mention':
                sender_tg_id = entity.user.id
    try:
        text = update.effective_message.text
    except(AttributeError):
        text = update.effective_message.caption

    if sender_tg_id:
        sender = User.query.filter_by(tg_id=sender_tg_id).first()
        bot.send_message(chat_id=sender.tg_id,
                         text=text)


@with_app_context
def location_message(update: Update, context):
    sender = User.query.filter_by(tg_id=update.message.from_user.id).first()
    location = update.message.location
    moderators = sender.get_group().moderators
    for user in moderators:
        response = bot.send_message(chat_id=user.tg_id,
                                    text=f'{texts.tg_user_mention(sender)} прислал геопозицию',
                                    parse_mode=ParseMode.MARKDOWN)
        bot.send_location(chat_id=user.tg_id,
                          location=location,
                          reply_to_message_id=response.message_id)


@with_app_context
def contact_message(update, context):
    update.effective_message.delete()
    sender = User.query.filter_by(tg_id=update.message.from_user.id).first()
    contact = update.message.contact
    if sender.status == 'wait_for_phone':
        sender.phone = contact.phone_number
        sender.status = ''
        # db.session.merge(sender)
        db.session.commit()
        greet_user(sender)
        return
    else:
        moderators = sender.get_group().moderators
        for user in moderators:
            response = bot.send_message(chat_id=user.tg_id,
                                        text=f'{texts.tg_user_mention(sender)} прислал контакт',
                                        parse_mode=ParseMode.MARKDOWN)
            bot.send_contact(chat_id=user.tg_id,
                             contact=contact,
                             reply_to_message_id=response.message_id)


@with_app_context
def photo_message(update: Update, context):
    sender = User.query.filter_by(tg_id=update.message.from_user.id).first()
    text = update.effective_message.caption

    moderators = sender.get_group().moderators
    for user in moderators:
        response = bot.send_photo(chat_id=user.tg_id,
                                  photo=update.effective_message.photo[-1].file_id,
                                  caption=f'{texts.tg_user_mention(sender)}:\n\n{text}',
                                  parse_mode=ParseMode.MARKDOWN)
    return 'ok'


@with_app_context
def video_message(update, context):
    try:
        caption = update.message.caption
    except:
        caption = ''
    sender = User.query.filter_by(tg_id=update.message.from_user.id).first()
    file_id = update.message.video
    moderators = sender.get_group().moderators
    for user in moderators:
        response = bot.send_video(chat_id=user.tg_id,
                                  caption=f'{texts.tg_user_mention(sender)}: {caption}',
                                  parse_mode='Markdown',
                                  video=file_id)


@with_app_context
def document_message(update: Update, context):
    try:
        caption = update.message.caption
    except:
        caption = ''
    sender = User.query.filter_by(tg_id=update.message.from_user.id).first()
    file_id = update.message.document.file_id
    moderators = sender.get_group().moderators
    for user in moderators:
        response = bot.send_document(chat_id=user.tg_id,
                                     caption=f'{texts.tg_user_mention(sender)}: {caption}',
                                     parse_mode='Markdown',
                                     document=file_id)


@with_app_context
def native_poll_message(update: Poll, context):
    sender = User.query.filter_by(tg_id=update.message.from_user.id).first()
    if sender.role == 'admin':
        pass
    else:
        pass


@with_app_context
def poll_message(update, context):
    users_answer = update.poll_answer.option_ids
    user = User.query.filter_by(tg_id=update.poll_answer.user.id).first()
    quiz = Quiz.query.get(int(user.status.split('_')[1]))
    current_question_index = int(user.status.split('_')[-1])
    current_question: Question = quiz.questions()[current_question_index]
    answer_type = current_question.answer_type
    right = set(users_answer) == set(current_question.get_right_answers())

    if answer_type == 'text':
        try:
            response = bot.send_message(chat_id=user.tg_id,
                                        text=quiz.questions()[current_question_index].right_answer_text if right else
                                        quiz.questions()[current_question_index].wrong_answer_text)
        except Exception as e:
            print(f'Произошла ошибка: {e}')

    elif answer_type == 'photo':
        try:
            response = bot.send_photo(chat_id=user.tg_id,
                                      photo=quiz.questions()[current_question_index].answer_content,
                                      caption=quiz.questions()[current_question_index].right_answer_text if right else
                                      quiz.questions()[current_question_index].wrong_answer_text)
        except Exception as e:
            print(f'Произошла ошибка: {e}')
    elif answer_type == 'video':
        try:
            response = bot.send_video(chat_id=user.tg_id,
                                      video=quiz.questions()[current_question_index].answer_content,
                                      caption=quiz.questions()[current_question_index].right_answer_text if right else
                                      quiz.questions()[current_question_index].wrong_answer_text)
        except Exception as e:
            print(f'Произошла ошибка: {e}')
    elif answer_type == 'audio':
        try:
            response = bot.send_audio(chat_id=user.tg_id,
                                      audio=quiz.questions()[current_question_index].answer_content,
                                      caption=quiz.questions()[current_question_index].right_answer_text if right else
                                      quiz.questions()[current_question_index].wrong_answer_text)
        except Exception as e:
            print(f'Произошла ошибка: {e}')

    # записать ответ пользователя
    user_question = UserQuestion.query.filter(UserQuestion.user_id == user.id,
                                              UserQuestion.question_id == current_question.id).first()
    if not user_question:
        user_question = UserQuestion()
    user_question.user_id = user.id
    user_question.question_id = current_question.id
    user_question.right = right
    user_question.answer = current_question.get_answer_by_index(users_answer[0])
    db.session.add(user_question)
    db.session.commit()

    # если еще есть вопросы - шлем следующий
    if current_question_index + 1 < len(quiz.questions()):
        user.status = f'playQuiz_{quiz.id}_{current_question_index + 1}'
        db.session.commit()
        send_question(user=user, quiz=quiz)
    # иначе отдаем финальный текст
    else:
        # считаем количество правильных ответов пользователя
        right_answers_count = len(UserQuestion.query.filter(UserQuestion.user_id == user.id,
                                                            UserQuestion.right.is_(True),
                                                            UserQuestion.question_id.in_(
                                                                [x.id for x in quiz.questions()])).all())
        # считаем количество вопросов
        questions_count = len(quiz.questions())

        quiz_result = f'Правильных ответов {right_answers_count} из {questions_count}'

        try:
            if quiz.final_text:
                response = bot.send_message(chat_id=user.tg_id,
                                            text=f'{quiz.final_text}\n\n*{quiz_result}*',
                                            parse_mode='Markdown')
            else:
                response = bot.send_message(chat_id=user.tg_id,
                                            text=f'Спасибо за участие!\n\n*{quiz_result}*',
                                            parse_mode='Markdown')
            reward_user(user, quiz)
        except Exception as e:
            print(f'Произошла ошибка: {e}')

        user.status = ''
        db.session.commit()


@with_app_context
def audio_message(update, context):
    sender = User.query.filter(User.tg_id == update.message.from_user.id).first()
    moderators = sender.get_group().moderators
    for moderator in moderators:
        bot.send_voice(chat_id=moderator.tg_id,
                       voice=update.message.voice,
                       caption=f'Аудио от {sender.id} {texts.tg_user_mention(sender)}',
                       parse_mode='Markdown')


def start_quiz(update, context):
    from app import create_app
    app = create_app(config_class=Config)
    with app.app_context():
        quiz_id = update.callback_query.data.split('_')[-1]
        quiz = Quiz.query.get(quiz_id)
        message_id = update.callback_query.message.message_id
        user = User.query.filter_by(tg_id=update.callback_query.from_user.id).first()
        user.status = f'playQuiz_{quiz.id}_0'
        db.session.commit()
        bot.edit_message_text(chat_id=user.tg_id,
                              text=f'Викторина *"{quiz.name}"*',
                              message_id=message_id,
                              parse_mode='Markdown')
        send_question(user=user, quiz=quiz, question_number=0)


def send_question(update=None, context=None, user=None, quiz=None, question_number=-1):
    from app import create_app
    app = create_app(config_class=Config)
    with app.app_context():
        if not user:
            user: User = User.query.filter_by(tg_id=update.callback_query.from_user.id).first()
        if not quiz:
            quiz: Quiz = Quiz.query.get(user.status.split('_')[1])
        if question_number < 0:
            question_number = int(user.status.split('_')[-1])

        variants = quiz.questions()[question_number].question_variants.split('\n')
        correct_option_id = ''
        options = []

        for index, option in enumerate(variants):
            if not option.split(' ')[-1].strip() == '(верный)':
                options.append(option.strip())
            else:
                options.append(option.strip().split('(верный)')[0])
                correct_option_id = index

        question_type = quiz.questions()[question_number].question_type

        if question_type == 'photo':
            if len(quiz.questions()[question_number].question_content.split(',')) > 1:
                media = []
                for m in quiz.questions()[question_number].question_content.split(','):
                    media.append(InputMediaPhoto(media=m))
                response = bot.send_media_group(chat_id=user.tg_id,
                                                media=media)
            else:
                response = bot.send_photo(chat_id=user.tg_id,
                                          photo=quiz.questions()[question_number].question_content)
        elif question_type == 'video':
            response = bot.send_video(chat_id=user.tg_id,
                                      video=quiz.questions()[question_number].question_content)
        elif question_type == 'audio':
            response = bot.send_audio(chat_id=user.tg_id,
                                      audio=quiz.questions()[question_number].question_content)

        response = bot.send_poll(
            chat_id=user.tg_id,
            question=quiz.questions()[question_number].question_text,
            options=json.dumps(options),
            type='quiz',
            correct_option_id=correct_option_id,
            explanation=quiz.questions()[question_number].answer_explanation,
            is_anonymous=False,
            explanation_parse_mode=ParseMode.MARKDOWN
        )


def create_button_map(buttons, col_count):
    button_map = []
    row_count = math.ceil(len(buttons) / col_count)
    current_button = 0
    for i in range(row_count):
        button_map.append([])
        for j in range(col_count):
            if current_button < len(buttons):
                button_map[len(button_map) - 1].append(buttons[current_button])
                current_button += 1
    return button_map


def get_inline_menu(button_lists):
    buttons = []
    item_count = -1
    for item in button_lists:
        if isinstance(item, list):
            item_count += 1
            buttons.append([])
            for subitem in item:
                inline_button = {
                    'text': f'{subitem["text"]}',
                    'callback_data': f'{subitem["data"]}'
                }
                buttons[item_count].append(inline_button)
        else:
            item_count += 1
            inline_button = {
                'text': f'{item["text"]}',
                'callback_data': f'{item["data"]}'
            }
            buttons.append([inline_button])

    ReplyKeyboardMarkup = {
        'inline_keyboard': buttons
    }
    return json.dumps(ReplyKeyboardMarkup)


def reward_user(user, quiz):
    wrong_answers_count = len(UserQuestion.query.filter(UserQuestion.user_id == user.id,
                                                        UserQuestion.right.is_(False),
                                                        UserQuestion.question_id.in_(
                                                            [x.id for x in quiz.questions()])).all())

    if wrong_answers_count == 0:
        bot.send_message(chat_id=user.tg_id,
                         text='Вы прошли викторину без ошибок. Ловите ваши бонусы. \n\nКстати, ваш баланс бонусов можно посмотреть по команде /bonus',
                         parse_mode=ParseMode.MARKDOWN)
        # создаем бонусы
        user_bonus: UserBonus = UserBonus()
        user_bonus.user = user.id
        user_bonus.amount = 50
        user_bonus.reason = f'Успешное участие в викторине #{quiz.id} {quiz.name}'
        db.session.add(user_bonus)
        db.session.commit()
    else:
        bot.send_message(chat_id=user.tg_id,
                         text='''
Вы прошли викторину с ошибками😔, к сожалению в этот раз бонусы вам не достанутся. 
Но мы верим🙏что в следующей викторине вам повезет❤️
                         ''',
                         parse_mode=ParseMode.MARKDOWN)
