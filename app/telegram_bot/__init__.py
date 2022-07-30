from flask import Blueprint

bp = Blueprint('telegram_bot', __name__)

from app.telegram_bot import routes