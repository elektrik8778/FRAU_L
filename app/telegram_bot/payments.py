from app.models import Food, FoodOrder, User, UserBonus
from app.telegram_bot.helpers import with_app_context
from app import db, bot
# from app.models import UserTrip
from telegram import Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
from pprint import pprint
from app import Config


@with_app_context
def pre_checkout(update: Update, context):
    order = FoodOrder.query.get(update.pre_checkout_query.invoice_payload.split("#")[1])
    u: User = User.query.filter_by(tg_id=update.effective_user.id).first()
    if update.pre_checkout_query.order_info.phone_number:
        u.phone = update.pre_checkout_query.order_info.phone_number
    db.session.commit()
    if order.uses_bonus and (order.used_bonuses > u.get_users_bonuses_amount()):
        bot.answer_pre_checkout_query(pre_checkout_query_id=update.pre_checkout_query.id,
                                      ok=False,
                                      error_message='У вас не хватает бонусов')
        return
    if order.paid:
        bot.answer_pre_checkout_query(pre_checkout_query_id=update.pre_checkout_query.id,
                                      ok=False,
                                      error_message='Этот заказ уже оплачен')
        return
    bot.answer_pre_checkout_query(pre_checkout_query_id=update.pre_checkout_query.id,
                                      ok=True)
    return 'ok'


@with_app_context
def successful_payment(update: Update, context):
    order: FoodOrder = FoodOrder.query.get(int(update.effective_message.successful_payment.invoice_payload.split("#")[1]))
    order.cost = update.effective_message.successful_payment.total_amount/100
    order.provider_payment_charge_id = update.effective_message.successful_payment.provider_payment_charge_id
    order.telegram_payment_charge_id = update.effective_message.successful_payment.telegram_payment_charge_id
    db.session.commit()
    order.set_paid()
    return 'ok'
