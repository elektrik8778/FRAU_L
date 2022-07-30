from flask import Blueprint

bp = Blueprint('admin', __name__)

from app.admin import routes
from app.telegram_bot.helpers import with_app_context
from app.models import Group, ShopAddr, User
from app import db
import os

@with_app_context
def check_groups():
    try:
        if len(Group.query.all()) == 0:
            group = Group()
            group.name = 'def'
            group.time_zone = 9
            db.session.add(group)
            db.session.commit()
            print(f'def Group created, id={group.id}')
        else:
            print(f'def group exists, id={Group.query.order_by(Group.id).first().id}')
    except Exception as e:
        print(e)


@with_app_context
def create_admin():
    try:
        if len(User.query.all()) == 0:
            admin = User()
            admin.first_name = 'admin'
            admin.tg_id = os.environ.get('ADMIN_TG_ID')
            admin.email = os.environ.get('ADMIN_EMAIL')
            admin.phone = os.environ.get('ADMIN_PHONE')
            admin.set_password('admin')
            admin.role = 'admin'
            admin.group = Group.query.order_by(Group.id).first().id
            db.session.add(admin)
            db.session.commit()
            print(f'admin created, id={admin.id}')
        else:
            print(f'admin exists, id={User.query.order_by(User.id).first().id}')
    except Exception as e:
        print(e)
        
@with_app_context
def create_def_shop():
    try:
        sa = ShopAddr(id=-1, addr='any')
        db.session.add(sa)
        db.session.commit()
    except:
        print("Shop ID:-1 exists")
        
        

create_def_shop()
check_groups()
create_admin()
