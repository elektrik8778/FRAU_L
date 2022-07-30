from app import db, bot
from app.main import bp
# from app.main.routes import send_messages_in_background
from app.models import User
from app.telegram_bot import texts, handlers
from flask import render_template, request, session
from datetime import datetime
from telegram import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
import json
import requests

@bp.route('/show_drawn_numbers', methods=['GET', 'POST'])
def show_drawn_numbers():
    return render_template('lotto/__loto_numbers_show.html')


@bp.route('/get_drawn_numbers', methods=['GET', 'POST'])
def get_drawn_numbers():
    drawn_numbers: DrawnNumber = DrawnNumber.query.order_by(DrawnNumber.id.desc()).all()
    numbers_dict = {}
    for index, n in enumerate(drawn_numbers):
        numbers_dict[f'number_{index+1}'] = n.number
    return json.dumps(numbers_dict)


@bp.route('/text_message', methods=['GET', 'POST'])
def text_message_handler():
    try:
        req = request.json
        user = User.query.get(int(req['data']['user']))
        text = req['data']['message']
        user_mention = texts.tg_user_mention(user)

        moderators = list(user.get_group().moderators)

        message = Message()
        message.type = 'text'
        message.content = {}
        message.user_id = user.id
        message.direction = 'outcome'
        message.date_time = datetime.now()
        message.local_link = ''
        message.file_id = ''
        db.session.add(message)
        db.session.commit()

        buttons = [
            InlineKeyboardButton(text='В эфир', callback_data=f'alertMessage_{message.id}'),
            InlineKeyboardButton(text='Удалить', callback_data=f'deleteMessage_{message.id}'),
            InlineKeyboardButton(text='В личку', url=f'tg://user?id={user.tg_id}')
        ]
        reply_markup = InlineKeyboardMarkup([buttons])
        response = None
        for moderator in moderators:
            response = bot.send_message(chat_id=moderator.tg_id,
                                        text=text,
                                        reply_markup=reply_markup,
                                        parse_mode=ParseMode.MARKDOWN)
        if response:
            message.content = response.to_json()

        db.session.commit()
    except:
        return 'без вложения'
    return 'ok'


@bp.route('/update_chat', methods=['GET', 'POST'])
def update_user_chat():
    try:
        req = json.loads(request.data)['request']
        messages_dict = {'data': []}
        response = ''
        if req == 'alert':
            current_message = ChatMessages.query.order_by(ChatMessages.id).filter(ChatMessages.shown.is_(False)).first()
            message_type = Message.query.filter_by(id=current_message.message_id).first().type
            if message_type == 'text':
                username = f'{User.query.get(Message.query.get(current_message.message_id).user_id).first_name} {User.query.get(Message.query.get(current_message.message_id).user_id).first_name}'
                text = json.loads(Message.query.get(current_message.message_id).content)['text']
                messages_dict['data'].append({'user': username, 'text': text})
                current_message.shown = True
                db.session.commit()
            if message_type == 'photo':
                try:
                    photozone = current_message.description.count('фотозона')
                except:
                    photozone = 0
                if not photozone:
                    username = f'{User.query.get(Message.query.get(current_message.message_id).user_id).first_name} {User.query.get(Message.query.get(current_message.message_id).user_id).first_name}'
                    text = ''
                    try:
                        print(json.loads(Message.query.get(current_message.message_id).content))
                        text = json.loads(Message.query.get(current_message.message_id).content)['caption']
                    except:
                        pass
                    link = ''
                    try:
                        link = './static' + Message.query.get(current_message.message_id).local_link.split('static')[1]
                    except:
                        pass
                    messages_dict['data'].append({'user': username, 'text': text, 'link': link})
                    current_message.shown = True
                    db.session.commit()
            response = json.dumps(messages_dict)
            return response
        elif req == 'chat' or req == 'marquee':
            messages_list = []
            if req == 'chat':
                messages_list = Message.query.order_by(Message.id.desc()).limit(50)
            if req == 'marquee':
                messages_list = Message.query.filter(Message.type.ilike('text')).order_by(Message.id.desc()).limit(20)
            for message in messages_list:
                if message.type == 'text' and message.direction == 'outcome':
                    username = User.query.get(message.user_id).first_name
                    text = json.loads(message.content)['text']
                    messages_dict['data'].append({'user': username, 'text': text})
                if message.type == 'photo' and message.direction == 'outcome':
                    username = User.query.get(message.user_id).first_name
                    text = ''
                    try:
                        text = json.loads(message.content)['message']['caption']
                    except:
                        pass
                    link=''
                    try:
                        link = './static'+message.local_link.split('static')[1]
                    except:
                        pass
                    messages_dict['data'].append({'user': username, 'text': text, 'link': link})
            response = json.dumps(messages_dict)
            return response
    except:
        return 'не грузит'


@bp.route('/connected', methods=['POST'])
def new_client():
    print(session)
    data = json.loads(request.get_data())['data']
    print(data)
    return 'ok'
