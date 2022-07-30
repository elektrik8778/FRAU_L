import os
import os.path
import hashlib
import re
import shutil
from app.api import bp
from flask import redirect, request, render_template, url_for, flash, Response
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from app import db, Config
from app.models import Food, FoodPhoto
from app.telegram_bot.handlers import get_inline_menu, create_button_map
from telegram.error import Unauthorized
from telegram import ParseMode
from datetime import datetime
import datetime
import threading
from io import StringIO
import csv
from flask import make_response


@bp.route("/api/food/csv", methods=["GET","POST"])
def csv_exp():
    # employee_info = ['id', 'category', 'food_name', 'description', 'price', 'available']
    foods = Food.query.order_by('id').all()
    csvList = [(x.to_dict()) for x in foods[:5]]
    csvList = str(re.sub('\[|\]', '', str(csvList)))
    print(csvList)
    # with open('test4.csv', 'w') as csvfile:
    #     writer = csv.DictWriter(csvfile, fieldnames=employee_info)
    #     writer.writeheader()
    #     writer.writerows(csvList)
    si = StringIO()
    cw = csv.writer(si)
    cw.writerows(csvList)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=export.csv"
    output.headers["Content-type"] = "text/csv"
    return output
    # return redirect(url_for("admin.foods"))


@bp.route("/api/food/add", methods=["POST"])
def add_food():
    # print(request)
    if current_user.role == 'admin' or current_user.role == 'moderator':
        d = Food(food_name=request.form["title"],
            description=request.form["good_desc"].replace("\n\n", "<br>"),
            price=float(request.form["price"]),
            category=int(request.form["category"]),
            available=bool(True if request.form.get('avail') else False),
            )
        try:
            db.session.add(d)
            db.session.commit()
        except:
            pass
        # print(request.files.keys())
        for i in request.files.keys():
            if i.startswith("image_"):
                l=request.files[i]
                if l.filename == "":
                    continue
                filename = str(hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest())[:6]+secure_filename(l.filename)
                fname = str(os.path.join(Config.UPLOAD_FOLDER, filename))
                l.save(fname)
                img = FoodPhoto(belongs_to=d.id, local_path=fname, filename=filename, main=i.endswith("_0"))
                db.session.add(img)
                db.session.flush()
        db.session.commit()
        db.session.close()
        return redirect(url_for("admin.foods"))


@bp.route("/api/food/rm/<cid>")
def rm_food(cid):
    if current_user.role == 'admin' or current_user.role == 'moderator':
        d = Food.query.filter_by(id=cid).first()
        db.session.delete(d)
        db.session.commit()
        return redirect(url_for("admin.foods"))
    
    
@bp.patch("/api/food/toggle/<int:fid>")
def toggle_food(fid):
    if current_user.role == 'admin' or current_user.role == 'moderator':
        d = Food.query.filter_by(id=fid).first()
        d.available = not d.available
        db.session.merge(d)
        db.session.commit()
        return Response(status=204)

@bp.post("/api/food/edit/<cid>")
def edit_food(cid):
    if current_user.role == 'admin' or current_user.role == 'moderator':
        d = Food.query.filter_by(id=cid).first()
        r = request.form
        d.food_name = r['title']
        d.description = r['good_desc']
        d.category = r['category']
        d.price = r['price']
        d.available = True if r.get('avail') else False
        db.session.merge(d)
        db.session.commit()
        for i in request.files.keys():
            if i.startswith("image_"):
                l=request.files[i]
                if l.filename == "":
                    continue
                filename = str(hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest())[:6]+secure_filename(l.filename)
                fname = str(os.path.join(Config.UPLOAD_FOLDER, filename))
                l.save(fname)
                img = FoodPhoto(belongs_to=d.id, local_path=fname, filename=filename)
                db.session.add(img)
                db.session.flush()
        db.session.commit()
        return redirect(url_for('admin.foods'))
    
    
@bp.delete("/api/food/photo/delete/<id>")
def delete_photo(id):
    if current_user.role == 'admin' or current_user.role == 'moderator':
        pic = FoodPhoto.query.get(id)
        try:
            os.remove(pic.local_path)
        except:
            pass
        db.session.delete(pic)
        db.session.commit()
        return Response(status=204)