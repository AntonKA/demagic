from demagic.analyze.expressions import analyze_expression, load_catalog


def test_catalog_loads():
    catalog = load_catalog()
    assert catalog["Trim"]["python"] == "{0}.strip()"


def test_known_functions_mapped():
    res = analyze_expression("Trim(Name)")
    assert res.functions == ["Trim"]
    assert res.unmapped == []


def test_unknown_functions_flagged():
    res = analyze_expression("MysteryFn(X) + Trim(Y)")
    assert "MysteryFn" in res.unmapped
    assert "Trim" in res.functions


def test_no_functions():
    res = analyze_expression("CustomerID>0")
    assert res.functions == []
    assert res.unmapped == []
