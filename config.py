import os
from dotenv import load_dotenv


basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config(object):
    #server
    SERVER = f'https://{os.environ.get("TG_ADDR")}'
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sdlasdkjfh834970987zldskfj843723o42'
    WTF_CSRF_SECRET_KEY = os.environ.get('SECRET_KEY') or 'wtf-key-secret-secret'
    TG_TOKEN = os.environ.get('TG_TOKEN') or None
    TG_ADMIN = os.environ.get('TG_ADMIN') or None

    # PostgresqlDB
    user = os.environ.get('POSTGRES_USER')
    pw = os.environ.get('POSTGRES_PW')
    url = os.environ.get('POSTGRES_URL')
    db = os.environ.get('POSTGRES_DB')
    SQLALCHEMY_DATABASE_URI = f'postgresql+psycopg2://{user}:{pw}@{url}/{db}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    USERS_PER_PAGE = 20
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    STATIC_FOLDER = os.path.join(basedir, 'app', 'static')
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'ogg', 'mp4', 'avi'}
    SERVER_TIME_ZONE = os.environ.get('SERVER_TIME_ZONE') or 0
    BOT_NAME = os.environ.get('BOT_NAME')
    STREAM_LINK = os.environ.get('STREAM_LINK')
    VIDGET_PREFIX = os.environ.get('VIDGET_PREFIX')

    # Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = os.environ.get('MAIL_PORT')
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') or False
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL') or False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')


    MAX_DISCOUNT = int(os.environ.get("MAX_BONUS_DISC"))
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
