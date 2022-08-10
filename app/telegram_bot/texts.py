import time
from app import bot
from app.models import User
from telegram import ParseMode
import os


def tg_user_mention(user):
    return f'[{user.first_name}](tg://user?id={user.tg_id})'


def greeting(user):
    text = f'''
*Привет, {user.first_name.strip()}, это уютный сервис чистоты в Благовещенске!*

Клининговые услуги для дома и предприятия
Выездная химчистка

👇🏻 Чтобы выбрать услуги, нажми кнопку "Заказ уборки"
'''
    return text


def success_registration(user: User):
    text = f'''
*УРА, {user.first_name.strip()}!* 🎈🎈🎈

Ну что же! Наконец-то все эти формальности позади! 😉 

Вы молодец, *регистрация прошла успешно!* 😁👌🏼

Скорее нажимайте на *главное меню*, чтобы узнать обо всех возможностях бота!
'''
    return text


def help(user):
    reply_markup = None
    text = f'{user.first_name}, твой запрос на техподдержку принят.\n' \
           f'Помощники с тобой свяжутся при ближайшей возможности.'
    try:
        bot.send_animation(chat_id=user.tg_id,
                           animation=open('app/static/images/bot_images/help.fid', 'r').read(),
                           caption=text,
                           reply_markup=reply_markup,
                           parse_mode=ParseMode.MARKDOWN)
    except:
        msg = bot.send_animation(chat_id=user.tg_id,
                                 animation=open('app/static/images/bot_images/help.gif', 'rb'),
                                 caption=text,
                                 reply_markup=reply_markup,
                                 parse_mode=ParseMode.MARKDOWN)
        with open('app/static/images/bot_images/help.fid', 'w') as f:
            f.write(msg.animation.file_id)

    for moderator in user.get_group().moderators:
        bot.send_message(chat_id=moderator.tg_id,
                         text=
                         f'🆘<a href="tg://user?id={user.tg_id}">{user.first_name}</a> просит помощи\n'
                         f'Данные:\n'
                         f'<b>id</b>: {user.id}\n'
                         f'<b>tg_id:</b> {user.tg_id}\n'
                         f'<b>телефон:</b> {user.phone}\n'
                         f'<b>почта:</b> {user.email}',
                         parse_mode=ParseMode.HTML)
        time.sleep(1)

    return 'ok'


def trips():
    return f'''
В кнопках под этим сообщением экскурсии, которые у нас есть на данный момент.

_Со значком ✅ отображаются уже оплаченые Вами экскурсии_
    '''


def pay_for_trip():
    return f'''
Мы в тестовом режиме, нормальную оплату прикрутим чуть позже.

А пока вы можете оплатить экскурсию переводом на карту Сбера:

*{os.environ.get("CARD_NUM")}*

Нажмите на номер, чтобы скопировать.
    '''

