from datetime import date

from closet_intelligence import db
from closet_intelligence.models import CalendarEntry, ClothingItem, Outfit, WearHistory


def register(client, email="user@example.com"):
    return client.post("/auth/register", data={"name": "Wardrobe User", "email": email, "password": "password123"})


def test_private_routes_require_auth(app):
    client = app.test_client()
    assert client.get("/wardrobe").status_code == 302
    assert client.get("/planner").status_code == 302


def test_outfit_wear_updates_items_and_is_idempotent(app):
    client = app.test_client()
    register(client)
    with app.app_context():
        user_id = 1
        top = ClothingItem(user_id=user_id, name="Top", category="Tops", primary_colour="cream")
        bottom = ClothingItem(user_id=user_id, name="Bottom", category="Bottoms", primary_colour="navy")
        shoes = ClothingItem(user_id=user_id, name="Shoes", category="Shoes", primary_colour="brown")
        db.session.add_all([top, bottom, shoes])
        db.session.flush()
        outfit = Outfit(user_id=user_id, occasion="Casual")
        db.session.add(outfit)
        db.session.flush()
        from closet_intelligence.models import OutfitItem
        db.session.add_all([OutfitItem(outfit_id=outfit.id, clothing_item_id=item.id, role=item.category) for item in (top, bottom, shoes)])
        db.session.commit()
        outfit_id = outfit.id
    assert client.post(f"/outfits/{outfit_id}/worn").status_code == 302
    assert client.post(f"/outfits/{outfit_id}/worn").status_code == 302
    with app.app_context():
        assert WearHistory.query.count() == 1
        assert all(item.worn_count == 1 for item in ClothingItem.query.all())


def test_planner_rejects_other_users_outfit(app):
    client = app.test_client()
    register(client)
    with app.app_context():
        outfit = Outfit(user_id=999, occasion="Casual")
        db.session.add(outfit)
        db.session.commit()
        outfit_id = outfit.id
    response = client.post("/planner/add", data={"outfit_id": outfit_id, "planned_date": date.today().isoformat()})
    assert response.status_code == 404
    with app.app_context():
        assert CalendarEntry.query.count() == 0
