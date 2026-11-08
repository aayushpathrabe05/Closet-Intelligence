import pytest
from closet_intelligence import create_app
from closet_intelligence.models import ClothingItem

@pytest.fixture
def app():
    return create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "WTF_CSRF_ENABLED": False})

@pytest.fixture
def fake_items():
    class Item:
        def __init__(self, id, category, colour, availability="Clean"):
            self.id, self.category, self.primary_colour, self.availability = id, category, colour, availability
            self.formality, self.style = 3, "Versatile"
        def occasion_list(self): return ["Casual"]
    return [Item(1, "Tops", "white"), Item(2, "Bottoms", "navy"), Item(3, "Shoes", "brown")]
