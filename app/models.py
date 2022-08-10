import json
from email.policy import default
from app import db, login, Config, bot
from flask import render_template, render_template_string
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import CheckConstraint
import jwt
from time import time
import requests
from telegram import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, \
    InputMediaAudio
from googleapiclient.discovery import build
from google.oauth2 import service_account
import os
import random
# import cv2
import uuid
from io import BufferedReader


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


group_moderators = db.Table('group_moderators',
                            db.Column('group_id', db.Integer, db.ForeignKey('group.id')),
                            db.Column('user_id', db.Integer, db.ForeignKey('user.id'))
                            )


class UserTag(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.id', ondelete='CASCADE'))
    receipt_date = db.Column(db.DateTime, default=datetime.now())


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tg_id = db.Column(db.BIGINT, index=True, unique=True)
    username = db.Column(db.String(64), index=True)
    is_bot = db.Column(db.Boolean, index=True, default=False)
    first_name = db.Column(db.String(64), index=True)
    last_name = db.Column(db.String(64), index=True)
    language_code = db.Column(db.String(5), index=True, default='ru')
    password_hash = db.Column(db.String(128))
    email = db.Column(db.Text)
    phone = db.Column(db.Text)
    status = db.Column(db.String(30), index=True, default='')
    role = db.Column(db.String(12), index=True, default='user')
    group = db.Column(db.Integer, db.ForeignKey('group.id'))
    registered = db.Column(db.DateTime, index=True, nullable=True, default=datetime.now())
    unsubscribed = db.Column(db.Boolean, default=False)
    promo_codes = db.Column(db.JSON)
    bonus_pts = db.Column(db.Integer, default=0)

    def set_unsubscribed(self):
        self.unsubscribed = True
        db.session.commit()

    def set_subscribed(self):
        self.unsubscribed = False
        db.session.commit()

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_group(self):
        if self.group:
            return Group.query.filter_by(id=self.group).first()

    def get_tags(self):
        return Tag.query.join(UserTag, Tag.id == UserTag.tag_id).filter(UserTag.user_id == self.id).all()

    def add_tag(self, tag):
        if not UserTag.query.filter(UserTag.tag_id == tag.id, UserTag.user_id == self.id).first():
            ut = UserTag()
            ut.user_id = self.id
            ut.tag_id = tag.id
            db.session.add(ut)
            db.session.commit()
            return Tag.query.get(tag.id).name

    def del_tag(self, tag):
        if ut := UserTag.query.filter(UserTag.tag_id == tag.id, UserTag.user_id == self.id).first():
            db.session.delete(ut)
            db.session.commit()
            return Tag.query.get(tag.id).name

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {
                'reset_password': self.id,
                'exp': time() + expires_in
            },
            Config.SECRET_KEY,
            algorithm='HS256')

    def get_received_scheduled_messages(self):
        return [r.id for r in self.received]

    def create_lottery_number(self, reason, description=''):
        ln = LotteryNumber()
        ln.user_id = self.id
        ln.reason = reason
        ln.description = description
        db.session.add(ln)
        db.session.commit()
        return ln

    def get_lottery_numbers(self):
        return LotteryNumber.query.filter(LotteryNumber.user_id == self.id).all()

    def get_lottery_cards(self):
        # https://lotto.idurn.ru/api/get_cards_list/<game_id>/<owner_id>/<api_token>
        resp = requests.get(
            f'{Config.LOTTO_URL}/get_cards_list/{self.get_group().lotto_game_id}/{self.tg_id}/{Config.LOTTO_API_TOKEN}')
        return sorted(resp.json())

    def add_lottery_cards(self, count=1):
        # '/create_card/<game_id>/<owner_id>/<api_token>'
        cards = []
        for i in range(count):
            cards.append(requests.get(f'{Config.LOTTO_URL}/create_card/{self.get_group().lotto_game_id}/{self.tg_id}/{Config.LOTTO_API_TOKEN}'))
        return cards

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)

    def set_item(self, item, value):
        if item in self.__dict__:
            setattr(self, item, value)
            db.session.commit()
        else:
            raise Exception('WrongItem')

    def __repr__(self):
        return f'{self.first_name}'

    def get_quest_tasks(self):
        return UserQuestTask.query.filter(UserQuestTask.user == self.id).all()

    def write_to_google_sheet(self):
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        SERVICE_ACCOUNT_FILE = os.path.join(Config.STATIC_FOLDER, 'json', 'credentials.json')
        SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
        SHEET_RANGE = 'Пользователи'
        credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=credentials)
        sheet = service.spreadsheets()

        # result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=USERS_RANGE, majorDimension='ROWS').execute()
        # values = result.get('values', [])
        # print(values)

        new_values = {
            'values': [[self.id, self.tg_id, self.first_name, str(self.registered), f'tg://user?id={self.tg_id}']]}

        response = sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=SHEET_RANGE,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=new_values).execute()

    def get_addresses(self):
        return UserAddresses.query.filter(UserAddresses.user == self.id).order_by(UserAddresses.id).all()

    def get_users_bonuses_list(self):
        return UserBonus.query.filter(UserBonus.user == self.id).all()

    def get_users_bonuses_amount(self):
        amount = 0
        for b in UserBonus.query.filter(UserBonus.user == self.id).all():
            amount += b.amount
        return amount

    def get_orders(self):
        return FoodOrder.query.filter(FoodOrder.owner == self.id).all()


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(30), index=True)
    time_zone = db.Column(db.Integer, default=9)
    lotto_game_id = db.Column(db.Integer)
    inst = db.Column(db.Text)
    code = db.Column(db.String(10))
    moderators = db.relationship('User',
                                 secondary=group_moderators,
                                 lazy='subquery',
                                 backref=db.backref('moderators', lazy=True))
    users = db.relationship('User', backref='users', lazy=True)

    def __repr__(self):
        return self.name


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(30), index=True)
    description = db.Column(db.String(128), index=True)


class ScheduledMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    message_type = db.Column(db.String(20), nullable=False)
    date_time = db.Column(db.DateTime)
    text = db.Column(db.String(4096), nullable=False)
    content_link = db.Column(db.String(256), nullable=False)
    group = db.Column(db.Integer, db.ForeignKey('group.id'))
    sent = db.Column(db.Boolean, default=False)

    def get_tasks_for_sending(self, sent=False, deleted=False):
        if sent and not deleted:
            return TaskForSending.query.filter(TaskForSending.scheduled_message_id == self.id,
                                               TaskForSending.sent.is_(sent)).all()
        if sent and deleted:
            return TaskForSending.query.filter(TaskForSending.scheduled_message_id == self.id,
                                               TaskForSending.sent.is_(sent),
                                               TaskForSending.deleted.is_(sent)).all()
        else:
            return TaskForSending.query.filter(TaskForSending.task_id == self.id).all()


class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(4096))
    final_text = db.Column(db.String(4096))
    final_callback = db.Column(db.String(128), default=None)
    command = db.Column(db.Text)

    def questions(self):
        return Question.query.filter(Question.quiz_id == self.id).all()


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'))
    question_type = db.Column(db.String(20), nullable=False)
    question_text = db.Column(db.String(1024), nullable=False)
    question_variants = db.Column(db.String(1024), nullable=False)
    question_content = db.Column(db.String(1024))
    question_content_link = db.Column(db.String(1024))
    answer_type = db.Column(db.String(1024), nullable=False)
    right_answer_text = db.Column(db.String(1024))
    wrong_answer_text = db.Column(db.String(1024))
    answer_explanation = db.Column(db.String(1024))
    answer_content = db.Column(db.String(1024))
    answer_content_link = db.Column(db.String(1024))

    def quiz(self):
        return Quiz.query.get(self.quiz_id)

    def get_right_answers(self):
        return [index for index, x in enumerate(self.question_variants.split('\n')) if '(верный)' in x]

    def get_answer_by_index(self, index):
        return self.question_variants.split('\n')[index].split('(верный)')[0].strip()


class UserQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'))
    answer = db.Column(db.Text)
    right = db.Column(db.Boolean)


class TaskForSending(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    scheduled_message_id = db.Column(db.Integer, db.ForeignKey('scheduled_message.id', ondelete='CASCADE'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    plan_sending_time = db.Column(db.DateTime)
    sent = db.Column(db.Boolean, default=False)
    message_id = db.Column(db.Integer, default=None)
    fact_sending_time = db.Column(db.DateTime)
    deleted = db.Column(db.Boolean, default=False)
    deleted_time = db.Column(db.DateTime)
    comment = db.Column(db.Text)

    def get_schedule_message(self):
        return ScheduledMessage.query.get(self.scheduled_message_id)

    def get_scheduled_message_type(self):
        task = ScheduledMessage.query.get(self.scheduled_message_id)
        return task.message_type

    def get_user(self):
        return User.query.get(int(self.user_id))

    def set_deleted(self):
        self.deleted = True
        db.session.commit()


class FoodOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_json = db.Column(db.JSON)
    owner = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    payment_type = db.Column(db.String, default="card")
    cost = db.Column(db.Float)
    paid = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime)
    status = db.Column(db.String(255), default="created")
    provider_payment_charge_id = db.Column(db.String(255))
    telegram_payment_charge_id = db.Column(db.String(255))
    msg_id = db.Column(db.String(255))
    invoice_msg_id = db.Column(db.String(255))
    admin_messages_ids = db.Column(db.ARRAY(item_type=db.String))
    order_type = db.Column(db.String(255))
    order_time = db.Column(db.String(255))
    fastest_delivery = db.Column(db.Boolean, default=False)
    comment = db.Column(db.Text)
    uses_bonus = db.Column(db.Boolean)
    delivery_to = db.Column(db.Integer, db.ForeignKey('user_addresses.id', ondelete='SET NULL'))
    delivery_price = db.Column(db.Integer, default=0)
    at_shop = db.Column(db.Integer, db.ForeignKey('shop_addr.id', ondelete='SET NULL'))
    used_bonuses = db.Column(db.Integer, default=0)
    used_promo = db.Column(db.Integer, db.ForeignKey('promocode.id', ondelete='SET NULL'))
    cost_after_discounts = db.Column(db.Float)
    seen = db.Column(db.Boolean, default=False)

    __table_args__ = (
        CheckConstraint(status.in_(['cancelled','created', 'paid', 'in progress', 'ready', 'in delivery', 'complete'])),
        CheckConstraint(order_type.in_(['delivery', 'self-checkout', 'at-place'])),
    )

    def get_user(self):
        return User.query.get(self.owner)

    def get_promo(self):
        return Promocode.query.get(self.used_promo)

    def get_food_order_content(self):
        return '\n'.join([f'*{i+1}. {Food.query.get(f["food"]).food_name if Food.query.get(f["food"]) else f["food_name"]+" (удалён)" if "food_name" in f else "(удалён)"}* {f["amount"]} шт.' for i,f in enumerate(json.loads(self.order_json))])

    def get_delivery_address(self):
        try:
            return UserAddresses.query.get(self.delivery_to).addr
        except:
            return '-'

    def get_payment_type(self):
        types = {
            'card in place': 'картой при получении',
            'online payment': 'онлайн оплата',
            'cash': 'наличными при получении'
        }
        return types[self.payment_type] if self.payment_type in types else '-'

    def get_order_type(self):
        types = {
            'delivery': 'доставка',
            'self-checkout': 'с собой',
            'at-place': 'на месте'
        }
        return types[self.order_type] if self.order_type in types else '-'

    def get_total_price(self):
        amount = self.cost
        if self.used_promo:
            amount -= amount*self.get_promo().discount
        if self.uses_bonus:
            amount -= self.used_bonuses
        if self.delivery_price:
            amount += self.delivery_price/100
        return amount

    def get_order_text(self):
        from app.telegram_bot.texts import tg_user_mention
        delta = timedelta(hours=int(self.get_user().get_group().time_zone) - int(os.environ.get('SERVER_TIME_ZONE')))
        text = f'''
*Заказ №{self.id}* от {(self.created_at + delta).strftime("%d.%m.%y %H:%M")}
*Время:* {self.order_time if not self.fastest_delivery else 'как можно скорее'}
*Статус:* {FoodOrder.to_ru(self.status)} {(self.paid_at + delta).strftime("%d.%m.%y %H:%M") if self.paid else ''}
*Метод оплаты:* {self.get_payment_type()}
*Скидка по промокоду:* {f'{self.get_promo().name} {self.get_promo().discount*100}%' if self.used_promo else 'нет'}
*Оплата бонусами:* {f'{self.used_bonuses} бонусов' if self.uses_bonus else 'нет'}
*Сумма:* {self.cost}
*Сумма с доставкой, скидкой и бонусами:* {self.get_total_price()}
*Клиент:* {tg_user_mention(self.get_user())}
*Адрес:* {self.get_delivery_address() if self.order_type == 'delivery' else '-'}
*Телефон:* {self.get_user().phone}
*В заказе:*
{self.get_food_order_content()}
*Комментарий:* {self.comment}
                             '''
        return text

    def get_order_html(self):
        try:
            delta = timedelta(hours=int(self.get_user().get_group().time_zone) - int(os.environ.get('SERVER_TIME_ZONE')))
        except:
            delta = timedelta(hours=0)
        food_list = ''
        for s in self.get_food_order_content().split('\n'):
            food_list += f'<li>{s.replace("*", "")}</li>'
        html = f'''
<h1>Заказ №{self.id} от {(self.created_at + delta).strftime("%d.%m.%y %H:%M")}</h1>
<p><b>Время:</b> {self.order_time if not self.fastest_delivery else 'как можно скорее'}</p> 
<p><b>Статус:</b> {FoodOrder.to_ru(self.status)} {(self.paid_at + delta).strftime("%d.%m.%y %H:%M") if self.paid else ''}</p> 
<p><b>Метод оплаты:</b> {self.get_payment_type()}</p>
<p><b>Скидка по промокоду:</b> {f'{self.get_promo().name} {self.get_promo().discount*100}%' if self.used_promo else 'нет'}</p>
<p><b>Оплата бонусами:</b> {f'{self.used_bonuses} бонусов' if self.uses_bonus else 'нет'}</p>
<p><b>Сумма:</b> {self.cost}</p>
<p><b>Сумма со скидкой и бонусами:</b> {self.get_total_price()}</p>
<p><b>Клиент:</b> {self.get_user().first_name if self.get_user() else '-'}</p>
<p><b>Адрес:</b> {self.get_delivery_address() if self.order_type == 'delivery' else '-'}</p>  
<p><b>Телефон:</b> {self.get_user().phone if self.get_user() else '-'}</p> 
<p><b>В заказе:</b></p>
<ul>
{food_list}
</ul>
<p><b>Комментарий:</b> {self.comment}</p>

{'' if self.paid else f'<a href="https://{os.environ.get("TG_ADDR")}/set_order_paid/{self.id}">Нажмите сюда, чтобы пометить этот заказ оплаченным</a>'}

{'' if self.paid else f'<p><a href="https://{os.environ.get("TG_ADDR")}/cancel_order/{self.id}" style="color: red;">Нажмите сюда, чтобы отменить этот заказ</a></p>'}
'''
        return html

    def apply_promo(self, id=None, code=None):
        if id:
            self.used_promo = Promocode.query.get(id)
            return
        if code:
            self.used_promo = Promocode.query.get(code)
            return

    def get_order_clients_reply_markup(self):
        btn_delivery_terms = InlineKeyboardButton('Условия доставки', url='https://telegra.ph/Usloviya-dostavki-05-31')
        btn_confident_policy = InlineKeyboardButton('Политика конфиценциальности', url='https://telegra.ph/Politika-konficencialnosti-05-31')
        btn_bonuses_terms = InlineKeyboardButton('Правила начисления бонусов', url='https://telegra.ph/Pravila-nachisleniya-bonusov-05-31')
        btn_cancel_order = InlineKeyboardButton('Отменить заказ', callback_data=f'cancelorder_{self.id}')
        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[[btn_delivery_terms], [btn_bonuses_terms], [btn_confident_policy]])
        if not self.paid:
            reply_markup.inline_keyboard.append([btn_cancel_order])
        return reply_markup

    def get_order_admins_reply_markup(self):
        btn_cancel_order = InlineKeyboardButton('Отменить заказ', callback_data=f'cancelorder_{self.id}')
        paid_btn = InlineKeyboardButton(text='Пометить оплаченым', callback_data=f'setpaid_{self.id}')

        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[])
        if not self.paid:
            reply_markup.inline_keyboard.append([paid_btn])
            reply_markup.inline_keyboard.append([btn_cancel_order])
        return reply_markup if len(reply_markup.inline_keyboard)>0 else None

    def set_paid(self):
        if not self.paid:
            self.paid = True
            self.status = 'paid'
            self.paid_at = datetime.now()
            self.seen = True
            if self.uses_bonus:
                # если пользователь выбрал "Оплатить заказ бонусами"
                user_bonus = UserBonus()
                user_bonus.user = self.owner
                user_bonus.amount = self.used_bonuses * -1
                user_bonus.reason = f'потрачено на заказ #{self.id}'
                db.session.add(user_bonus)
            db.session.commit()

            # начисляем бонусы за чек
            bonus_for_order = 0
            bonus_txt = ''
            if 2000 <= self.get_total_price() <= 2999:
                bonus_for_order = 100
                bonus_txt = f'заказ от 2 до 3 тысяч #{self.id}'
            elif self.get_total_price() >= 3000:
                bonus_for_order = 200
                bonus_txt = f'заказ от 3 тысяч #{self.id}'
            if bonus_for_order > 0:
                user_bonus = UserBonus()
                user_bonus.user = self.owner
                user_bonus.amount = bonus_for_order
                user_bonus.reason = bonus_txt
                db.session.add(user_bonus)
                db.session.commit()

            try:
                for msg in self.admin_messages_ids:
                    bot.edit_message_text(chat_id=int(msg.split('_')[0]),
                                          message_id=int(msg.split('_')[-1]),
                                          text=self.get_order_text(),
                                          reply_markup=self.get_order_admins_reply_markup(),
                                          parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                print(e)
            try:
                additional_information = f'''
_В течении 15 минут с Вами свяжется оператор. Если оператор не позвонит, свяжитесь, пожалуйста, с ним по номеру 56-56-88 и скажите номер заказа #{self.id}_
                    '''
                bot.edit_message_text(chat_id=User.query.get(self.owner).tg_id,
                                      message_id=self.msg_id,
                                      text=f'*Спасибо! Ваш заказ оплачен.*\n\n{self.get_order_text()}\n\n{additional_information}',
                                      reply_markup=self.get_order_clients_reply_markup(),
                                      parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                print(e)

    def cancel(self):
        if not self.paid:
            # удалить все сообщения
            try:
                for msg in self.admin_messages_ids:
                    bot.delete_message(chat_id=int(msg.split('_')[0]),
                                       message_id=int(msg.split('_')[-1]))
            except Exception as e:
                print(e)

            if self.msg_id:
                try:
                    bot.delete_message(chat_id=User.query.get(self.owner).tg_id,
                                       message_id=self.msg_id)
                except Exception as e:
                    print(e)

            if self.invoice_msg_id:
                try:
                    bot.delete_message(chat_id=User.query.get(self.owner).tg_id,
                                       message_id=self.invoice_msg_id)
                except Exception as e:
                    print(e)

            # удалить сам заказ
            db.session.delete(self)
            db.session.commit()
        else:
            assert 'Оплаченный заказ не может быть удалён'

    @staticmethod
    def to_ru(status):
        statuses = dict(zip(['cancelled', 'created', 'paid', 'in progress', 'ready', 'in delivery', 'complete'],["Отменён","Создан", "Оплачен", "В работе", "Готов", "В доставке", "Закончен"]))
        try:
            return statuses[status]
        except:
            return status


class Food(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.Integer, db.ForeignKey('food_category.id', ondelete='CASCADE'), nullable=False)
    food_name = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float(), default=0, nullable=False)
    available = db.Column(db.Boolean(), default=False)
    photos = db.relationship('FoodPhoto', cascade='all, delete')

    def get_category_name(self):
        return FoodCategory.query.get(self.category).cat_name

    def to_dict(self):
        result = {
            'id': self.id,
            'category': self.category,
            'food_name': self.food_name,
            'description': self.description,
            'price': self.price,
            'available': self.available,
            # 'photos': [{
            #     'file_type': f.file_type,
            #     'filename': f.filename
            # } for f in self.photos]
        }
        return result


class FoodCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cat_name = db.Column(db.String(256), nullable=False, unique=True)
    cat_picture = db.Column(db.String(256))

    def get_foods(self):
        return Food.query.filter(Food.category == self.id).all()


class FoodPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    main = db.Column(db.Boolean, default=False)
    belongs_to = db.Column(db.Integer, db.ForeignKey("food.id", ondelete='CASCADE'), nullable=False, )
    file_type = db.Column(db.String(256), default="photo")
    local_path = db.Column(db.String(512), nullable=False)
    filename = db.Column(db.String(512))
    telegram_id = db.Column(db.String(512))


class FoodCart(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uid = db.Column(db.BIGINT, db.ForeignKey('user.tg_id', ondelete='CASCADE'), nullable=False)
    food = db.Column(db.Integer, db.ForeignKey('food.id', ondelete='CASCADE'), nullable=False)
    food_name = db.Column(db.Text)
    amount = db.Column(db.Integer)

    def get_food(self) -> Food:
        return Food.query.get(self.food)

    def __to_dict__(self):
        return {'food': self.food, 'amount': self.amount, 'food_name': self.food_name}

    __table_args__ = (
        db.UniqueConstraint(uid, food),
    )


class UserAddresses(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.Text)
    addr = db.Column(db.Text, nullable=False)


class Promocode(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(16), unique=True, nullable=False)
    discount = db.Column(db.Float, nullable=False)
    name = db.Column(db.String(32))
    enabled = db.Column(db.Boolean)
    desc = db.Column(db.Text, default='')


class ShopAddr(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text)
    addr = db.Column(db.Text, nullable=False)


class UserBonus(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    amount = db.Column(db.Integer)
    reason = db.Column(db.Text)


class UserPromocode(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    promocode = db.Column(db.Integer, db.ForeignKey('promocode.id', ondelete='CASCADE'), nullable=False)
    order = db.Column(db.Integer, db.ForeignKey('food_order.id', ondelete='CASCADE'))
