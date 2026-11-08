import json
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from urllib.parse import urljoin, urlparse
from flask import abort, Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_user, logout_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from PIL import Image
from . import db
from .models import User, StyleProfile, ClothingItem, Outfit, OutfitItem, WearHistory, CalendarEntry
from .intelligence import recommend, gap_analysis

main_bp = Blueprint("main", __name__)
auth_bp = Blueprint("auth", __name__)

ALLOWED_CATEGORIES = {"Tops", "Bottoms", "Dresses", "Outerwear", "Shoes", "Bags", "Accessories"}
ALLOWED_AVAILABILITY = {"Clean", "In laundry", "Unavailable"}
ALLOWED_OCCASIONS = {"College", "Casual", "Office", "Interview", "Formal event", "Party", "Date", "Travel", "Wedding", "Festive event"}


def safe_next_url(target):
    if not target:
        return None
    candidate = urlparse(urljoin(request.host_url, target))
    if candidate.scheme in {"http", "https"} and candidate.netloc == request.host:
        return candidate.path + (f"?{candidate.query}" if candidate.query else "")
    return None


def normalize_text(value):
    return " ".join((value or "").strip().split())


def save_image(upload):
    if not upload or not upload.filename:
        return None
    try:
        image = Image.open(upload)
        image.verify()
        upload.seek(0)
        image = Image.open(upload)
        if image.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValueError
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        filename = f"{current_user.id}_{uuid4().hex}.webp"
        image.save(Path(current_app.config["UPLOAD_FOLDER"]) / filename, "WEBP", quality=88)
        return filename
    except (OSError, ValueError):
        raise ValueError("Please upload a valid JPG, PNG or WEBP image.")


def remove_image(filename):
    if not filename:
        return
    path = Path(current_app.config["UPLOAD_FOLDER"]) / Path(filename).name
    if path.is_file():
        path.unlink()

@main_bp.route("/")
def landing(): return render_template("landing.html")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated: return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        name, email, password = request.form.get("name", "").strip(), request.form.get("email", "").strip().lower(), request.form.get("password", "")
        if not name or len(name) > 120 or len(password) < 8 or "@" not in email or "." not in email.rsplit("@", 1)[-1]: flash("Please provide a name, valid email and password of at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first(): flash("That email is already part of the wardrobe.", "error")
        else:
            user = User(name=name, email=email); user.set_password(password); user.profile = StyleProfile(); db.session.add(user); db.session.commit(); login_user(user); return redirect(url_for("main.dashboard"))
    return render_template("auth/register.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
        if user and user.check_password(request.form.get("password", "")): login_user(user); return redirect(safe_next_url(request.args.get("next")) or url_for("main.dashboard"))
        flash("The details did not match our records.", "error")
    return render_template("auth/login.html")

@auth_bp.post("/logout")
@login_required
def logout(): logout_user(); return redirect(url_for("main.landing"))


@main_bp.get("/images/<path:filename>")
@login_required
def private_image(filename):
    item = ClothingItem.query.filter_by(user_id=current_user.id, image_path=Path(filename).name).first()
    if not item:
        abort(404)
    path = Path(current_app.config["UPLOAD_FOLDER"]) / item.image_path
    if path.is_file():
        return send_file(path)
    abort(404)

@main_bp.route("/dashboard")
@login_required
def dashboard():
    recent = ClothingItem.query.filter_by(user_id=current_user.id).order_by(ClothingItem.created_at.desc()).limit(4).all()
    outfit = Outfit.query.filter_by(user_id=current_user.id).order_by(Outfit.created_at.desc()).first()
    return render_template("dashboard.html", recent=recent, outfit=outfit, total=len(current_user.items), today=date.today().strftime("%A, %d %B %Y"))

@main_bp.route("/wardrobe")
@login_required
def wardrobe():
    query = ClothingItem.query.filter_by(user_id=current_user.id)
    search = request.args.get("q", "").strip(); category = request.args.get("category", ""); colour = request.args.get("colour", ""); style = request.args.get("style", ""); season = request.args.get("season", ""); availability = request.args.get("availability", ""); sort = request.args.get("sort", "recent")
    if search: query = query.filter(or_(ClothingItem.name.ilike(f"%{search}%"), ClothingItem.primary_colour.ilike(f"%{search}%")))
    if category in ALLOWED_CATEGORIES: query = query.filter_by(category=category)
    if colour: query = query.filter(ClothingItem.primary_colour.ilike(f"%{colour}%"))
    if style: query = query.filter(ClothingItem.style.ilike(f"%{style}%"))
    if season: query = query.filter_by(season=season)
    if availability in ALLOWED_AVAILABILITY: query = query.filter_by(availability=availability)
    ordering = {"recent": ClothingItem.created_at.desc(), "most-worn": ClothingItem.worn_count.desc(), "least-worn": ClothingItem.worn_count.asc()}.get(sort, ClothingItem.created_at.desc())
    items = query.order_by(ordering).all()
    return render_template("wardrobe.html", items=items, search=search, category=category, colour=colour, style=style, season=season, availability=availability, sort=sort)

@main_bp.route("/wardrobe/new", methods=["GET", "POST"])
@login_required
def new_item(): return clothing_form()

@main_bp.route("/wardrobe/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id): return clothing_form(ClothingItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404())

def clothing_form(item=None):
    if request.method == "POST":
        data = request.form
        category = data.get("category", "")
        availability = data.get("availability", "Clean")
        occasions = [value for value in request.form.getlist("occasions") if value in ALLOWED_OCCASIONS]
        try:
            formality = max(1, min(5, int(data.get("formality", 3))))
            purchase_price = max(0, float(data.get("purchase_price") or 0))
            purchase_date = date.fromisoformat(data["purchase_date"]) if data.get("purchase_date") else None
        except (TypeError, ValueError):
            flash("Please check the form values and dates.", "error"); return render_template("clothing_form.html", item=item)
        if not normalize_text(data.get("name")) or category not in ALLOWED_CATEGORIES or not normalize_text(data.get("primary_colour")) or availability not in ALLOWED_AVAILABILITY: flash("Please complete the required clothing details.", "error"); return render_template("clothing_form.html", item=item)
        if item is None: item = ClothingItem(user_id=current_user.id); db.session.add(item)
        for field in ("category", "primary_colour", "secondary_colour", "pattern", "style", "season", "availability"): setattr(item, field, normalize_text(data.get(field)) or None)
        item.name = normalize_text(data.get("name")); item.formality = formality; item.purchase_price = purchase_price; item.purchase_date = purchase_date; item.occasions = json.dumps(occasions)
        upload = request.files.get("image")
        if upload and upload.filename:
            try:
                previous = item.image_path
                item.image_path = save_image(upload)
                remove_image(previous)
            except ValueError as error:
                flash(str(error), "error"); return render_template("clothing_form.html", item=item)
        db.session.commit(); flash("Your wardrobe has been updated.", "success"); return redirect(url_for("main.wardrobe"))
    return render_template("clothing_form.html", item=item)

@main_bp.post("/wardrobe/<int:item_id>/delete")
@login_required
def delete_item(item_id):
    item = ClothingItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404(); remove_image(item.image_path); db.session.delete(item); db.session.commit(); flash("Piece removed.", "success"); return redirect(url_for("main.wardrobe"))

@main_bp.route("/studio", methods=["GET", "POST"])
@login_required
def studio():
    results = []
    if request.method == "POST":
        occasion = request.form.get("occasion", "Casual")
        try:
            temperature = max(-40, min(60, int(request.form.get("temperature", 20))))
        except ValueError:
            temperature = 20
        recent_ids = {item.id for history in WearHistory.query.filter_by(user_id=current_user.id).order_by(WearHistory.worn_date.desc()).limit(5).all() for item in Outfit.query.get(history.outfit_id).items} if WearHistory.query.filter_by(user_id=current_user.id).first() else set()
        results = recommend(current_user.items, occasion, {"temperature": temperature, "rain": request.form.get("rain") == "on"}, current_user.profile, recent_ids, request.form.getlist("excluded_categories"))
    saved_outfits = Outfit.query.filter_by(user_id=current_user.id).order_by(Outfit.created_at.desc()).limit(12).all()
    return render_template("studio.html", results=results, saved_outfits=saved_outfits)

@main_bp.post("/studio/save")
@login_required
def save_outfit():
    try:
        item_ids = {int(x) for x in request.form.getlist("item_ids")}
    except ValueError:
        flash("That outfit could not be saved.", "error"); return redirect(url_for("main.studio"))
    items = ClothingItem.query.filter(ClothingItem.user_id == current_user.id, ClothingItem.id.in_(item_ids), ClothingItem.availability == "Clean").all()
    if len(items) != len(item_ids) or not item_ids:
        flash("Only clean pieces from your wardrobe can be saved.", "error"); return redirect(url_for("main.studio"))
    occasion = request.form.get("occasion", "Casual")
    verified = recommend(items, occasion, {"temperature": int(request.form.get("temperature", 20)), "rain": request.form.get("rain") == "on"}, current_user.profile)
    match = next((result for result in verified if {item.id for item in result[1]} == item_ids), None)
    if not match:
        flash("That combination is not a valid outfit structure.", "error"); return redirect(url_for("main.studio"))
    score, _, breakdown, explanation = match
    outfit = Outfit(user_id=current_user.id, occasion=occasion, score=score, score_breakdown=json.dumps(breakdown), explanation=explanation); db.session.add(outfit); db.session.flush()
    for item in items: db.session.add(OutfitItem(outfit_id=outfit.id, clothing_item_id=item.id, role=item.category))
    db.session.commit(); flash("Outfit saved to your studio.", "success"); return redirect(url_for("main.studio"))


def mark_outfit_worn(outfit):
    today = date.today()
    if WearHistory.query.filter_by(user_id=current_user.id, outfit_id=outfit.id, worn_date=today).first():
        return False
    db.session.add(WearHistory(user_id=current_user.id, outfit_id=outfit.id, worn_date=today))
    for link in outfit.items:
        link.clothing_item.worn_count = (link.clothing_item.worn_count or 0) + 1
        link.clothing_item.last_worn_at = datetime.utcnow()
    for entry in CalendarEntry.query.filter_by(user_id=current_user.id, outfit_id=outfit.id, planned_date=today).all():
        entry.status = "worn"
    return True


@main_bp.post("/outfits/<int:outfit_id>/worn")
@login_required
def mark_worn(outfit_id):
    outfit = Outfit.query.filter_by(id=outfit_id, user_id=current_user.id).first_or_404()
    mark_outfit_worn(outfit); db.session.commit(); flash("Wear history updated.", "success"); return redirect(request.referrer or url_for("main.studio"))


@main_bp.post("/outfits/<int:outfit_id>/favourite")
@login_required
def toggle_favourite(outfit_id):
    outfit = Outfit.query.filter_by(id=outfit_id, user_id=current_user.id).first_or_404(); outfit.is_favourite = not outfit.is_favourite; db.session.commit(); return redirect(request.referrer or url_for("main.studio"))

@main_bp.route("/planner")
@login_required
def planner():
    try:
        start = date.fromisoformat(request.args.get("week", "")) if request.args.get("week") else date.today() - timedelta(days=date.today().weekday())
    except ValueError:
        start = date.today() - timedelta(days=date.today().weekday())
    entries = CalendarEntry.query.filter(CalendarEntry.user_id == current_user.id, CalendarEntry.planned_date.between(start, start + timedelta(days=6))).order_by(CalendarEntry.planned_date).all(); outfits = Outfit.query.filter_by(user_id=current_user.id).order_by(Outfit.created_at.desc()).all(); return render_template("planner.html", entries=entries, outfits=outfits, today=date.today(), week_start=start, week_days=[start + timedelta(days=offset) for offset in range(7)], previous_week=start - timedelta(days=7), next_week=start + timedelta(days=7))

@main_bp.post("/planner/add")
@login_required
def add_plan():
    outfit = Outfit.query.filter_by(id=request.form.get("outfit_id"), user_id=current_user.id).first_or_404()
    try: planned_date = date.fromisoformat(request.form.get("planned_date", ""))
    except ValueError: flash("Choose a valid calendar date.", "error"); return redirect(url_for("main.planner"))
    db.session.add(CalendarEntry(user_id=current_user.id, outfit_id=outfit.id, planned_date=planned_date)); db.session.commit(); return redirect(url_for("main.planner", week=planned_date - timedelta(days=planned_date.weekday())))


@main_bp.post("/planner/<int:entry_id>/delete")
@login_required
def delete_plan(entry_id):
    entry = CalendarEntry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404(); db.session.delete(entry); db.session.commit(); return redirect(url_for("main.planner"))


@main_bp.post("/planner/<int:entry_id>/worn")
@login_required
def planner_worn(entry_id):
    entry = CalendarEntry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404(); mark_outfit_worn(entry.outfit); entry.status = "worn"; db.session.commit(); return redirect(url_for("main.planner", week=entry.planned_date - timedelta(days=entry.planned_date.weekday())))

@main_bp.route("/insights")
@login_required
def insights():
    items = current_user.items; used = [x for x in items if x.worn_count]; utilization = round(len(used) / len(items) * 100) if items else 0; costs = [{"name": x.name, "value": round(x.purchase_price / x.worn_count, 2) if x.worn_count else x.purchase_price} for x in items]; return render_template("insights.html", items=items, used=used, utilization=utilization, costs=costs, gaps=gap_analysis(items))

@main_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.name = request.form.get("name", current_user.name); current_user.profile.put("preferred_colours", [value.strip() for value in request.form.get("preferred_colours", "").split(",") if value.strip()]); current_user.profile.put("preferred_styles", [value.strip() for value in request.form.get("preferred_styles", "").split(",") if value.strip()]); db.session.commit(); flash("Profile preferences saved.", "success")
    return render_template("profile.html")
