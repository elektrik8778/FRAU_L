import os
import os.path
import hashlib
import json
import time
from app.api import bp
from flask import redirect, request, render_template, url_for, flash, Response
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from app import db, Config
from app.models import Food, FoodOrder, FoodPhoto
from app.telegram_bot.handlers import get_inline_menu, create_button_map
from telegram.error import Unauthorized
from telegram import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
import datetime
import asyncio
from app.telegram_bot.handlers import bot
from app.helpers.scheduler import schedule
from app.helpers.context_wrapper import with_app_context


@with_app_context
def ask_back(order):
    bot.send_message(chat_id=order.get_user().tg_id,
                     text='Оставьте отзыв о заказе',
                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text='Перейти к форме', url=f'{Config.SERVER}/feedback?id={order.id}')]]))
    return


@bp.patch("/api/order/<id>")
def update_status(id):
    r = json.loads(request.data)
    order = FoodOrder.query.get(id)
    order.status = r['status']
    db.session.merge(order)
    db.session.commit()
    if order.status == 'complete':
        schedule(7200, ask_back, [order])
    return Response(status=204)


@bp.route('/api/set_order_seen/<oid>')
def set_order_seen(oid):
    FoodOrder.query.get(oid).seen = True
    db.session.commit()
    return 'ok'
