import os
import os.path
import hashlib
import json
from app.api import bp
from app.models import FoodCart, Promocode, UserAddresses, User, ShopAddr, UserPromocode, FoodOrder
from flask import redirect, request, render_template, url_for, flash, Response, g, send_from_directory, send_file
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from app import db, Config, bot
from app.models import Food, FoodPhoto, FoodCategory
from app.telegram_bot.handlers import get_inline_menu, create_button_map
from telegram.error import Unauthorized
from telegram import ParseMode
# from datetime import datetime
import datetime
import threading
from app.api.helpers import with_app_context


@bp.get('/api/get_cart/<uid>')
def get_cart(uid):
    cart: FoodCart = FoodCart.query.filter(FoodCart.uid == uid).order_by(FoodCart.id).all()
    g.cart = cart
    g.food = Food
    g.photo = FoodPhoto
    g.restaraunts = ShopAddr.query.filter(ShopAddr.id != -1).all()
    g.u = User.query.filter_by(tg_id=uid).first()
    return render_template('main/__cart_items.html')


@bp.get('/api/get_category_foods/<cid>')
def get_category_foods(cid):
    foods: Food = Food.query.filter(Food.category == cid).all()
    category: FoodCategory = FoodCategory.query.get(int(cid))
    return render_template('main/__category_foods.html', foods=foods, category=category)


@bp.get('/api/get_user_addresses/<uid>')
def get_user_addresses(uid):
    user: User = User.query.filter(User.tg_id == uid).first()
    return json.dumps([{'id': a.id, 'addr': a.addr, 'name': a.name} for a in user.get_addresses()])


@bp.get("/api/cart/empty/<int:cid>")
def is_empty_cart(cid):
    q = FoodCart.query.filter_by(uid=cid)
    json_resp = {"empty": not bool(q.count()), "items": {}}
    for i in q.all():
        json_resp['items'][i.food] = i.amount
    return Response(json.dumps(json_resp), mimetype="application/json")


@bp.put("/api/cart")
def add_to_cart():
    r = json.loads(request.data)

    if r['action'] == 'add':
        cart = FoodCart(uid=r['id'], food=r['fid'], food_name=Food.query.get(int(r['fid'])).food_name, amount=1)
        try:
            db.session.add(cart)
            db.session.commit()
        except:
            pass
    elif r['action'] == 'del':
        cart: FoodCart = FoodCart.query.filter(FoodCart.uid == r['id'],
                                               FoodCart.food == r['fid']).all()
        for c in cart:
            db.session.delete(c)
        db.session.commit()
    return Response(status=204)


@bp.patch('/api/cart/<op>')
def update_cart(op):
    r = json.loads(request.data)
    cart = FoodCart.query.filter_by(uid=r['uid'], food=r['fid']).first()
    if op == 'inc':
        cart.amount += 1
        db.session.merge(cart)
    elif op == 'dec':
        cart.amount -= 1
        if cart.amount == 0:
            db.session.delete(cart)
        else:
            db.session.merge(cart)
    else:
        return Response(status=400)
    db.session.commit()
    return Response(str(cart.amount), status=200)


@bp.delete('/api/cart')
def delete_cart():
    r = json.loads(request.data)
    cart = FoodCart.query.filter_by(uid=r['id'], food=r['fid']).first()
    db.session.delete(cart)
    db.session.commit()


@bp.post('/saveAddress')
def save_address():
    data = request.json
    print(data)
    addr = UserAddresses()
    addr.addr = data['address']
    addr.user = User.query.filter(User.tg_id == data['uid']).first().id
    if data['name']:
        addr.name = data['name']
    else:
        addr.name = ', '.join(i.strip() for i in data['address'].split(',')[2:4]).strip()
    db.session.add(addr)
    db.session.commit()
    return str(addr.id)


@bp.get('/api/checkcode')
def check_promo():
    try:
        code: Promocode = Promocode.query.filter(Promocode.code == request.values.get('code')).first()
    except:
        code = None
    if not code:
        j = {"valid": False,
             "enabled": False,
             "desc": "Промокод не найден"}
    else:
        user_promo: UserPromocode = UserPromocode.query.filter(UserPromocode.user == User.query.filter(User.tg_id == int(request.values.get('uid'))).first().id,
                                                               UserPromocode.promocode == code.id).first()
        if user_promo:
            j = {"valid": False,
                 "desc": 'Вы уже использовали этот промокод',
                 "enabled": False}
            return json.dumps(j)
        j = {"valid": True,
             "desc": code.desc,
             "enabled": code.enabled,
             "discount": code.discount,
             'id': code.id}
    return json.dumps(j)


@bp.get('/api/get_users_bonuses/<uid>')
def get_users_bonuses(uid):
    user: User = User.query.filter(User.tg_id == uid).first()
    amount = 0
    for b in user.get_users_bonuses_list():
        amount += b.amount
    return str(amount)


@bp.get('/set_order_paid/<oid>')
def set_order_paid(oid):
    order: FoodOrder = FoodOrder.query.get(int(oid))
    try:
        order.set_paid()
        return f'''{order.get_order_html()}'''
    except:
        return f'Заказ #{oid} не найден'


@bp.get('/cancel_order/<oid>')
def cancel_order(oid):
    order: FoodOrder = FoodOrder.query.get(int(oid))
    try:
        order.cancel()
        return f'Заказ #{oid} удалён'
    except Exception as e:
        return f'Заказ #{oid} не найден'


@bp.get('/data.geojson')
def get_geodata():
    return send_file(path_or_file=os.path.join(Config.STATIC_FOLDER, 'maps', 'lavashi.geojson'), mimetype='application/json')


@bp.get('/api/is_first_order/<uid>')
def is_first_order(uid):
    user: User = User.query.filter(User.tg_id == int(uid)).first()
    return Response(status=200) if len(user.get_orders()) == 0 else Response(status=204)
