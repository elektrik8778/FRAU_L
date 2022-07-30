from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from config import Config
import telegram
import logging
from telegram.ext import Dispatcher
from flask_cors import CORS
from flask_bootstrap import Bootstrap

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
login.login_message = u'Пожалуйста, авторизуйтесь, чтобы попасть на страницу трансляции.'
mail = Mail()
cors = CORS()
bootstrap = Bootstrap()

bot = telegram.Bot(token=Config.TG_TOKEN)
dispatcher = Dispatcher(bot=bot, update_queue=None, use_context=True)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    login.init_app(app)
    mail.init_app(app)
    bootstrap.init_app(app)
    cors.init_app(app, resources={
        r'/*': {'origins': '*'}
    })

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    from app.telegram_bot import bp as tg_bp
    app.register_blueprint(tg_bp)
    
    from app.api import bp as api_bp
    app.register_blueprint(api_bp)

    return app
