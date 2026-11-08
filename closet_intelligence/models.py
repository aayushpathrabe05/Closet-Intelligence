from datetime import datetime
import json
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    profile = db.relationship("StyleProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    items = db.relationship("ClothingItem", back_populates="user", cascade="all, delete-orphan")
    outfits = db.relationship("Outfit", back_populates="user", cascade="all, delete-orphan")
    wear_history = db.relationship("WearHistory", back_populates="user", cascade="all, delete-orphan")
    calendar_entries = db.relationship("CalendarEntry", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class StyleProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    preferred_colours = db.Column(db.Text, default="[]")
    preferred_styles = db.Column(db.Text, default="[]")
    preferred_occasions = db.Column(db.Text, default="[]")
    preferred_categories = db.Column(db.Text, default="[]")
    user = db.relationship("User", back_populates="profile")

    def get(self, field):
        return json.loads(getattr(self, field) or "[]")

    def put(self, field, values):
        setattr(self, field, json.dumps(values))


class ClothingItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(40), nullable=False, index=True)
    primary_colour = db.Column(db.String(40), nullable=False)
    secondary_colour = db.Column(db.String(40))
    pattern = db.Column(db.String(40), default="Solid")
    style = db.Column(db.String(40), default="Versatile")
    season = db.Column(db.String(40), default="All season")
    formality = db.Column(db.Integer, default=3)
    occasions = db.Column(db.Text, default="[]")
    image_path = db.Column(db.String(255))
    availability = db.Column(db.String(30), default="Clean")
    purchase_price = db.Column(db.Float, default=0)
    purchase_date = db.Column(db.Date)
    worn_count = db.Column(db.Integer, default=0)
    last_worn_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship("User", back_populates="items")

    def occasion_list(self):
        return json.loads(self.occasions or "[]")


class Outfit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    occasion = db.Column(db.String(40), nullable=False)
    score = db.Column(db.Float, default=0)
    score_breakdown = db.Column(db.Text, default="{}")
    explanation = db.Column(db.Text, default="")
    is_favourite = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship("User", back_populates="outfits")
    items = db.relationship("OutfitItem", back_populates="outfit", cascade="all, delete-orphan")
    wear_history = db.relationship("WearHistory", back_populates="outfit", cascade="all, delete-orphan")
    calendar_entries = db.relationship("CalendarEntry", back_populates="outfit", cascade="all, delete-orphan")

    def breakdown(self):
        return json.loads(self.score_breakdown or "{}")


class OutfitItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    outfit_id = db.Column(db.Integer, db.ForeignKey("outfit.id", ondelete="CASCADE"), nullable=False)
    clothing_item_id = db.Column(db.Integer, db.ForeignKey("clothing_item.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    outfit = db.relationship("Outfit", back_populates="items")
    clothing_item = db.relationship("ClothingItem")


class WearHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    outfit_id = db.Column(db.Integer, db.ForeignKey("outfit.id", ondelete="CASCADE"), nullable=False)
    worn_date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
    user = db.relationship("User", back_populates="wear_history")
    outfit = db.relationship("Outfit", back_populates="wear_history")


class CalendarEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    outfit_id = db.Column(db.Integer, db.ForeignKey("outfit.id", ondelete="CASCADE"), nullable=False)
    planned_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="planned")
    user = db.relationship("User", back_populates="calendar_entries")
    outfit = db.relationship("Outfit", back_populates="calendar_entries")
