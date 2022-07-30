import os

from app.api import bp
from flask import redirect, request, render_template, url_for, flash
from flask_login import login_required, current_user
from app import db, bot
from app.models import FoodCategory
from app.telegram_bot.handlers import get_inline_menu, create_button_map
from telegram.error import Unauthorized
from telegram import ParseMode
import datetime
from config import Config
import threading
import hashlib
from werkzeug.utils import secure_filename




@bp.route("/api/category/add", methods=["POST"])
def add_category():
    if current_user.role == 'admin' or current_user.role == 'moderator':
        d = FoodCategory()
        d.cat_name = request.form.get('cat_name')
        for i in request.files.keys():
            l=request.files[i]
            if l.filename == "":
                continue
            filename = str(hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest())[:6]+secure_filename(l.filename)
            fname = str(os.path.join(Config.UPLOAD_FOLDER, filename))
            l.save(fname)
            d.cat_picture=filename
        try:
            db.session.add(d)
            db.session.commit()
        except:
            flash("Категория с таким именем уже существует")
        return redirect(url_for("admin.categories"))


@bp.route("/api/category/rm/<cid>")
def rm_category(cid):
    if current_user.role == 'admin' or current_user.role == 'moderator':
        d = FoodCategory.query.filter_by(id=cid).first()
        db.session.delete(d)
        db.session.commit()
        return redirect(url_for("admin.categories"))
    

@bp.post("/api/category/edit/<cid>")
def edit_category(cid):
    if current_user.role == 'admin' or current_user.role == 'moderator':
        d = FoodCategory.query.filter_by(id=cid).first()
        d.cat_name = request.form.get("cat_name")
        for i in request.files.keys():
            l=request.files[i]
            if l.filename == "":
                continue
            filename = str(hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest())[:6]+secure_filename(l.filename)
            fname = str(os.path.join(Config.UPLOAD_FOLDER, filename))
            l.save(fname)
            d.cat_picture=filename
        try:
            db.session.add(d)
            db.session.commit()
        except:
            flash("Категория с таким именем уже существует")
        return redirect(url_for("admin.categories"))