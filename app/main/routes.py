import json
import os
from time import timezone

from app.main import bp
from flask import redirect, request, render_template, g
from flask_login import login_required, current_user
from app import db, bot
from app.models import Food, FoodCart, FoodPhoto, ScheduledMessage, ShopAddr, User, TaskForSending, Quiz, FoodCategory, FoodOrder
from app.telegram_bot.handlers import get_inline_menu, create_button_map
from telegram.error import Unauthorized
from telegram import ParseMode
from datetime import datetime, tzinfo
from config import Config
import threading
import ntplib


@bp.route('/')
def index_main():
    return redirect('/admin')


@bp.route('/categories')
def category_list():
    bot_name = Config.BOT_NAME
    title = 'Главная'
    fcs = FoodCategory.query.order_by(FoodCategory.id).all()
    g.restaraunts = ShopAddr.query.filter(ShopAddr.id != -1).all()
    orders_start_time = os.environ.get('ORDERS_START_TIME')
    orders_end_time = os.environ.get('ORDERS_END_TIME')
    yandex_api_key = os.environ.get('YA_MAPS_API_KEY')
    bot_payments = os.environ.get('BOT_PAYMETS')
    return render_template('main/new_categories.html',
                           title=title,
                           bot_name=bot_name,
                           orders_start_time=orders_start_time,
                           orders_end_time=orders_end_time,
                           yandex_api_key=yandex_api_key,
                           bot_payments=bot_payments,
                           fcs=fcs)


@bp.route('/menu', methods=['GET', 'POST'])
@bp.route('/menu/<fcid>', methods=['GET', 'POST'])
def index(fcid=None):
    bot_name = Config.BOT_NAME
    title = 'Главная'
    g.food = Food
    g.pics = FoodPhoto

    # with open(os.path.join(Config.STATIC_FOLDER, 'txt', 'Политика конфиденциальности.txt'), 'r') as text:
    #     confidence_text = text.readlines()

    return render_template('main/index.html',
                           bot_name=bot_name,
                           fcid=fcid,
                           title=title)
    # return redirect('/admin')


@bp.route("/cart/<id>")
def cart(id):
    cur_time = ntplib.datetime.datetime.utcnow().hour+9
    # print(cur_time)
    g.delivery_available = 10 <= cur_time <= 22
    g.u = User.query.filter_by(tg_id=id).first()
    g.cart = FoodCart.query.filter_by(uid=g.u.tg_id).order_by('id').all()
    g.food = Food
    g.photo = FoodPhoto
    g.restaraunts = ShopAddr.query.filter(ShopAddr.id!=-1).all()
    return render_template("main/cart.html")


@bp.route('/cron')
def cron():
    scheduled_messages = ScheduledMessage.query.all()

    for sm in scheduled_messages:
        db.session.execute(f'''
        insert into task_for_sending(user_id, scheduled_message_id, sent, deleted, plan_sending_time) (
            select "user".id, scheduled_message.id, false, false, now()
            from "user"
                inner join scheduled_message on scheduled_message.id = {sm.id}
                inner join "group" g on g.id = "user"."group"
            where "user".tg_id is not null and "user".id not in
            (
                select user_id
                from task_for_sending
                where task_for_sending.scheduled_message_id ={sm.id}
            )
            and scheduled_message.date_time <= cast('{datetime.now()}' as timestamp) - interval '{os.environ.get("SERVER_TIME_ZONE")} hour' + cast(cast(g.time_zone as text) || ' hour' as interval)
            and scheduled_message.sent is not true
            {'and "user"."group" = scheduled_message."group"' if sm.group else ''}
        );
        ''')
        tasks_for_this_sm: TaskForSending = TaskForSending.query.filter(TaskForSending.scheduled_message_id == sm.id).all()
        if tasks_for_this_sm:
            sm.sent = True
        db.session.commit()

    # Начинаем отправку запланированных
    thr = threading.Thread(target=send_tasks)
    thr.start()

    return 'ok'


def send_tasks():
    from app import create_app
    app = create_app(config_class=Config)
    with app.app_context():
        tasks: TaskForSending = TaskForSending.query.filter(TaskForSending.sent == False).all()
        for task in tasks:
            task_type = task.get_scheduled_message_type()
            user = User.query.get(task.user_id)
            scheduled_message = ScheduledMessage.query.get(task.scheduled_message_id)

            if task_type == 'text':
                text = scheduled_message.text
                try:
                    response = bot.send_message(chat_id=user.tg_id,
                                                text=text,
                                                parse_mode=ParseMode.MARKDOWN)
                    task.sent = True
                    task.message_id = response.message_id
                    task.fact_sending_time = response.date
                    db.session.commit()
                except Unauthorized:
                    user.set_unsubscribed()
                    task.comment = 'Пользователь отписался'
                    db.session.commit()
                except AttributeError:
                    print(f'AttributeError user_id={user}')
                    task.comment = 'AttributeError'
                    db.session.commit()
                except:
                    task.comment = 'Ошибка tg_id'
                    db.session.commit()

            if task_type == 'photo':
                caption = scheduled_message.text
                try:
                    response = bot.send_photo(chat_id=user.tg_id,
                                              photo=scheduled_message.content_link,
                                              caption=caption,
                                              parse_mode=ParseMode.MARKDOWN)
                    task.sent = True
                    task.message_id = response.message_id
                    task.fact_sending_time = response.date
                    db.session.commit()
                except Unauthorized:
                    user.set_unsubscribed()
                    task.comment = 'Пользователь отписался'
                    db.session.commit()
                except AttributeError:
                    print(f'AttributeError user_id={user}')
                    task.comment = 'AttributeError'
                    db.session.commit()
                except:
                    task.comment = 'Ошибка tg_id'
                    db.session.commit()
            if task_type == 'video':
                caption = scheduled_message.text
                try:
                    response = bot.send_video(chat_id=user.tg_id,
                                              video=scheduled_message.content_link,
                                              caption=caption,
                                              parse_mode=ParseMode.MARKDOWN)
                    task.sent = True
                    task.message_id = response.message_id
                    task.fact_sending_time = response.date
                    db.session.commit()
                except Unauthorized:
                    user.set_unsubscribed()
                    task.comment = 'Пользователь отписался'
                    db.session.commit()
                except AttributeError:
                    print(f'AttributeError user_id={user}')
                    task.comment = 'AttributeError'
                    db.session.commit()
                except:
                    task.comment = 'Ошибка tg_id'
                    db.session.commit()
            if task_type == 'poll':
                poll_id = int(scheduled_message.text)
                quiz = Quiz.query.get(poll_id)
                buttons = [
                    {
                        'text': 'Начинаем',
                        'data': f'startQuiz_{poll_id}'
                    }
                ]
                map = create_button_map(buttons, 1)
                reply_markup = get_inline_menu(map)
                try:
                    response = bot.send_message(chat_id=user.tg_id,
                                                text=quiz.description,
                                                parse_mode=ParseMode.MARKDOWN,
                                                reply_markup=reply_markup)
                    task.sent = True
                    task.message_id = response.message_id
                    task.fact_sending_time = response.date
                    db.session.commit()
                except Unauthorized:
                    user.set_unsubscribed()
                    task.comment = 'Пользователь отписался'
                    db.session.commit()
                except AttributeError:
                    print(f'AttributeError user_id={user}')
                    task.comment = 'AttributeError'
                    db.session.commit()
                except:
                    task.comment = 'Ошибка tg_id'
                    db.session.commit()
