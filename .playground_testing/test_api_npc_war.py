from engine.api import EbeeEngine


def _province(provinceid, ownercountry, controllercountry, troops, center):
    return {
        "id": provinceid,
        "ownercountry": ownercountry,
        "controllercountry": controllercountry,
        "country": controllercountry,
        "countrycolor": (100, 100, 100),
        "troops": troops,
        "center": center,
    }


def test_api_runnpcturn_supports_npc_vs_npc_wars():
    engine = EbeeEngine()
    engine.provincemap = {
        "A1": _province("A1", "A", "A", 0, (0.0, 0.0)),
        "B1": _province("B1", "B", "B", 40, (1.0, 0.0)),
        "C1": _province("C1", "C", "C", 8, (2.0, 0.0)),
    }
    engine.provincegraph = {
        "A1": set(),
        "B1": {"C1"},
        "C1": {"B1"},
    }
    engine.countrytocolorlookup = {
        "A": (10, 10, 10),
        "B": (20, 20, 20),
        "C": (30, 30, 30),
    }
    engine.playercountry = "A"

    engine.setupnpc(
        playercountry="A",
        economyconfig={
            "startinggold": 1000,
            "startingpopulation": 1000,
            "recruitamount": 10,
            "recruitgoldcostperunit": 1,
            "recruitpopulationcostperunit": 1,
            "mingoldincome": 0,
            "goldincomedivisor": 1,
            "minpopulationgrowth": 0,
            "populationgrowthdivisor": 1,
        },
    )
    engine.syncnpcwars(warpairset={("b", "c")})

    movementorderlist = []
    summary = engine.runnpcturn(movementorderlist)

    assert summary["invasionOrders"] >= 1
    assert any(
        (order["country"] == "B" and order["path"][-1] == "C1")
        or (order["country"] == "C" and order["path"][-1] == "B1")
        for order in movementorderlist
    )


def test_api_country_data_counts_owner_and_controller_in_one_pass():
    engine = EbeeEngine()
    engine.provincemap = {
        "A1": {**_province("A1", "A", "A", 4, (0.0, 0.0)), "parentstateid": "S1"},
        "A2": {**_province("A2", "A", "B", 7, (1.0, 0.0)), "parentstateid": "S1"},
        "B1": {**_province("B1", "B", "A", 5, (2.0, 0.0)), "parentstateid": "S2"},
    }
    engine.countrytocolorlookup = {"A": (10, 10, 10), "B": (20, 20, 20)}
    engine.scripteconomy = {"A": {"gold": 12, "population": 34}}

    data = engine.getcountrydata("a")

    assert data["country"] == "A"
    assert data["ownedProvinceCount"] == 2
    assert data["controlledProvinceCount"] == 2
    assert data["controlledTroops"] == 9
    assert data["ownedProvinceIds"] == ["A1", "A2"]
    assert data["controlledProvinceIds"] == ["A1", "B1"]
    assert data["ownedStateIds"] == ["S1"]
    assert data["controlledStateIds"] == ["S1", "S2"]
