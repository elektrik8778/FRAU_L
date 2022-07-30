import os

from app.api import bp
from flask import redirect, request, render_template, url_for, flash, Response
from flask_login import login_required, current_user
from app import db, bot
from app.models import FoodCategory, Promocode
from app.telegram_bot.handlers import get_inline_menu, create_button_map
from telegram.error import Unauthorized
from telegram import ParseMode
import datetime
from config import Config
import threading
import hashlib
from werkzeug.utils import secure_filename


@bp.route("/api/promo/toggle/<id>", methods=["PATCH"])
def togglepromo(id):
    if current_user.role == 'admin' or current_user.role == 'moderator':
        promo = Promocode.query.get(id)
        promo.enabled = not promo.enabled
        db.session.merge(promo)
        db.session.commit()
        return Response(status=204)
