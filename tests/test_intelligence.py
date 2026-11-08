from closet_intelligence.intelligence import colour_score, recommend

def test_colour_score_is_normalized(fake_items):
    assert 0 <= colour_score(fake_items[:2]) <= 100

def test_recommendations_only_use_clean_items(fake_items):
    fake_items[-1].availability = "In laundry"
    results = recommend(fake_items)
    assert all(item.availability == "Clean" for _, combo, _ in results for item in combo)
