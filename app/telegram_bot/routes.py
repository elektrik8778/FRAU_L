from app import bot, dispatcher
from app.telegram_bot import bp
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, Filters, CallbackQueryHandler, PollAnswerHandler, \
    ShippingQueryHandler, PreCheckoutQueryHandler
from threading import Thread
from app.telegram_bot import handlers, payments
import os
from flask import request
from pprint import pprint

dispatcher.add_handler(CommandHandler('users_count', handlers.command_users_count))

# current
dispatcher.add_handler(CommandHandler('start', handlers.command_start))
dispatcher.add_handler(CommandHandler('help', handlers.command_help))
dispatcher.add_handler(CommandHandler('test', handlers.command_test))
dispatcher.add_handler(CommandHandler('bonus', handlers.command_bonus))

dispatcher.add_handler(MessageHandler(Filters.reply, callback=handlers.reply_message))
dispatcher.add_handler(MessageHandler(Filters.photo, callback=handlers.photo_message))
dispatcher.add_handler(MessageHandler(Filters.video, callback=handlers.video_message))
dispatcher.add_handler(MessageHandler(Filters.document, callback=handlers.document_message))
dispatcher.add_handler(MessageHandler(Filters.contact, callback=handlers.contact_message))
dispatcher.add_handler(MessageHandler(Filters.voice, callback=handlers.audio_message))
dispatcher.add_handler(MessageHandler(Filters.location, callback=handlers.location_message))

dispatcher.add_handler(PollAnswerHandler(handlers.poll_message))
dispatcher.add_handler(CallbackQueryHandler(pattern='startQuiz', callback=handlers.start_quiz))
dispatcher.add_handler(CallbackQueryHandler(pattern='sendQuestion', callback=handlers.send_question))
dispatcher.add_handler(CallbackQueryHandler(pattern='help', callback=handlers.help))
dispatcher.add_handler(CallbackQueryHandler(pattern='deleteMessage', callback=handlers.delete_message))
dispatcher.add_handler(CallbackQueryHandler(pattern='setpaid', callback=handlers.set_order_paid))
dispatcher.add_handler(CallbackQueryHandler(pattern='cancelorder', callback=handlers.cancel_order))
dispatcher.add_handler(MessageHandler(Filters.text, callback=handlers.text_message))

# # payments
dispatcher.add_handler(PreCheckoutQueryHandler(callback=payments.pre_checkout))
dispatcher.add_handler(MessageHandler(Filters.successful_payment, callback=payments.successful_payment))


if (addr := os.environ.get("TG_ADDR")) != "":
    print("Setting webhook")
    res = bot.set_webhook(f'https://{addr}/telegram')
    print(res)


@bp.route('/telegram', methods=['GET', 'POST'])
def telegram():
    update = Update.de_json(request.get_json(force=True), bot=bot)
    # pprint(update.to_dict())
    thread = Thread(target=dispatcher.process_update, args=[update,])
    thread.start()
    thread.join()
    return 'ok'
