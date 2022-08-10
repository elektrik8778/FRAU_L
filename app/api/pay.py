import os
import os.path
import json
from app.api import bp
from app.models import FoodCart, FoodOrder, Promocode, User, UserPromocode
from flask import request, Response
from app import db, Config, mail
from app.models import Food
from telegram import ParseMode, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from app.telegram_bot.handlers import bot
from flask_mail import Message


@bp.get('/pay')
@bp.post('/pay')
def pay():
    # print(request.json)
    # return Response(status=200)
    uid = int(request.json['uid'])
    u: User = User.query.filter_by(tg_id=uid).first()
    o = FoodOrder()
    carts = FoodCart.query.filter_by(uid=uid).all()
    o.fastest_delivery = request.json['soonest']
    # o.at_shop = int(request.json['restraunt_id'])
    o.uses_bonus = request.json['use_bonus']
    o.comment = request.json['comment']
    o.order_type = 'delivery'
    o.used_promo = request.json['promocode'] or None

    try:
        o.delivery_to = int(request.json['delivery_addr'])
    except:
        pass
    o.order_time = request.json['prepare_at']
    o.payment_type = request.json['pm']
    order = []
    o.cost = 0
    prices = []
    items = []
    if not((o.order_time or o.fastest_delivery) or o.delivery_to):
        return Response(status=400)
    for i in carts:
        f = Food.query.filter_by(id=i.food).first()
        o.cost += f.price * i.amount
        prices.append(LabeledPrice(label=f.food_name, amount=int(int(f.price)*int(i.amount)*100)))
        items.append([f.food_name, i.amount])
        order.append(i.__to_dict__())

    # здесь считаем доставку
    # if o.order_type == 'delivery':
    #     prices.append(LabeledPrice(label="Доставка", amount=int(float(request.json['delivery_price'])*100)))
    #     o.delivery_price = int(float(request.json['delivery_price'])*100)

    if o.uses_bonus:
        discount = float(Config.MAX_DISCOUNT)/100.0
        if u.get_users_bonuses_amount() >= o.cost*discount:
            discount = o.cost*discount
        else:
            discount = u.get_users_bonuses_amount()
        o.used_bonuses = discount
        prices.append(LabeledPrice(label='Оплата бонусами', amount=int(discount*100*-1)))

    promo_cost = 0
    for i in prices:
        promo_cost += i.amount

    if o.used_promo:
        promo: Promocode = o.get_promo()
        discount_p = promo_cost * promo.discount
        promo_cost *= (1-promo.discount)
        prices.append(LabeledPrice(label=f'Промокод "{promo.name}"', amount=-int(discount_p)))
        user_promo = UserPromocode()
        user_promo.user = u.id
        user_promo.promocode = promo.id
        user_promo.order = o.id
        db.session.add(user_promo)

    o.cost_after_discounts = promo_cost

    o.order_json = json.dumps(order)
    o.owner = User.query.filter_by(tg_id=uid).first().id
    # ФОРМИРУЕМ ИНВОЙС и отправляем o.owner
    # оплаченным заказ помечается после оплаты
    # o.paid = True
    # o.paid_at = datetime.datetime.now()
    db.session.add(o)
    db.session.commit()
    if o.used_promo:
        promo: Promocode = o.get_promo()
        user_promo: UserPromocode = UserPromocode.query.filter(UserPromocode.user == u.id,
                                                               UserPromocode.promocode == promo.id).first()
        user_promo.order = o.id
        db.session.add(user_promo)
        db.session.commit()


    for i in carts:
        db.session.delete(i)

    description = "\n".join([f"{x[0]} - {x[1]} шт." for x in items])
    need_phone_number = False
    if not u.phone:
        need_phone_number = True

    # отправляем клиенту инвойс если оплата онлайн
    msg_id = ''
    pay_online_txt = ''
    if o.payment_type == 'online payment':
        pay_online_txt = '_Оплатите, пожалуйста, счет, который пришел в сообщении ниже._'

    # отправляем клиенту детальный заказ с кнопками информации
    additional_information = f'''
_В течении 15 минут с Вами свяжется оператор. Если оператор не позвонит, свяжитесь, пожалуйста, с ним по номеру {os.environ.get("OPERATOR_PHONE")} и скажите номер заказа #{o.id}_
    '''

    msg_id = bot.send_message(chat_id=u.tg_id,
                              text=f'*Спасибо! Ваш заказ получен.*\n{pay_online_txt}\n{o.get_order_text()}\n\n{additional_information}',
                              reply_markup=o.get_order_clients_reply_markup(),
                              parse_mode=ParseMode.MARKDOWN)
    o.msg_id = msg_id.message_id
    db.session.commit()

    if o.payment_type == 'online payment':
        invoice_msg = bot.send_invoice(
            chat_id=u.tg_id,
            title=f"Заказ #{o.id}",
            payload=f"order#{o.id}",
            start_parameter=int(f'{u.id}_{o.id}'),
            description=f"Оплата заказа #{o.id}",
            provider_token=os.environ.get('PAYMENT_TOKEN'),
            currency='RUB',
            prices=prices,
            protect_content=True,
            need_phone_number=need_phone_number,
            max_tip_amount=40000,
            suggested_tip_amounts=[9900, 19900, 29900]
        )
        o.invoice_msg_id = invoice_msg.message_id
        db.session.commit()

    # отправляем сообщение админам в бот
    admin_messages = []
    for i in User.query.filter_by(role='admin').all():
        try:
            msg = bot.send_message(chat_id=i.tg_id,
                                   text=o.get_order_text(),
                                   reply_markup=o.get_order_admins_reply_markup(),
                                   parse_mode=ParseMode.MARKDOWN)
            admin_messages.append(f'{i.tg_id}_{msg.message_id}')
        except Exception as e:
            print(e)
    o.admin_messages_ids = None
    o.admin_messages_ids = admin_messages
    db.session.commit()

    # отправляем e-mail
    try:
        subject = f"Заказ из телеграм бота #{o.id}"
        sender = Config.MAIL_DEFAULT_SENDER
        recipients = [Config.ADMIN_EMAIL]
        text_body = o.get_order_text().replace('*', '')
        html_body = o.get_order_html()
        send_order_mail(subject, sender, recipients, text_body, html_body)
    except:
        pass

    return Response(status=200)


def send_order_mail(subject, sender, recipients, text_body, html_body):
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    mail.send(msg)
    return 'ok'
