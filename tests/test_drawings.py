import pytest

from dxf_mcp import drawings


def test_summary_reports_units_layers_and_entity_mix(drawing_path):
    s = drawings.summarize(drawing_path)
    assert s.units == "millimeters"
    assert s.layer_count >= 5              # 0 plus the four added
    assert s.block_definition_count == 1   # PART; layout blocks excluded
    assert s.entity_types["LINE"] == 2
    assert s.entity_types["INSERT"] == 2
    assert "FRAME" in s.layers_in_use
    assert "UNUSED" not in s.layers_in_use


def test_layers_carry_entity_counts(drawing_path):
    by_name = {l.name: l for l in drawings.layers(drawing_path)}
    assert by_name["FRAME"].entity_count == 3   # two lines plus one blockref
    assert by_name["UNUSED"].entity_count == 0
    assert by_name["FRAME"].is_on


def test_bill_of_materials_flattens_attributes_into_rows(drawing_path):
    bom = drawings.bill_of_materials(drawing_path)
    assert bom.row_count == 2
    assert bom.attribute_columns == ["MATERIAL", "PARTNO", "QTY"]
    parts = {r.attributes["PARTNO"]: r for r in bom.rows}
    assert parts["CCI-1042"].attributes["QTY"] == "4"
    assert parts["CCI-1042"].attributes["MATERIAL"] == "Oak"
    assert parts["CCI-2088"].layer == "PANEL"


def test_bill_of_materials_filters_by_block_name(drawing_path):
    assert drawings.bill_of_materials(drawing_path, block="part").row_count == 2
    assert drawings.bill_of_materials(drawing_path, block="NOTHING").row_count == 0


def test_standards_flags_missing_and_forbidden_layers(drawing_path):
    report = drawings.check_standards(
        drawing_path, required_layers=["FRAME", "DIMENSIONS"], forbidden_layers=["PANEL"]
    )
    assert report.passed is False
    rules = [(f.rule, f.severity) for f in report.findings]
    assert ("required_layer", "error") in rules
    assert ("forbidden_layer", "error") in rules
    assert "DIMENSIONS" in " ".join(f.detail for f in report.findings)


def test_standards_layer_matching_is_case_insensitive(drawing_path):
    report = drawings.check_standards(drawing_path, required_layers=["frame", "Panel"])
    assert not [f for f in report.findings if f.rule == "required_layer"]


def test_standards_reports_empty_layers_as_warnings_only(drawing_path):
    report = drawings.check_standards(drawing_path)
    empties = [f for f in report.findings if f.rule == "empty_layer"]
    assert any("UNUSED" in f.detail for f in empties)
    assert all(f.severity == "warning" for f in empties)
    assert report.passed is True


def test_standards_checks_units(drawing_path):
    assert drawings.check_standards(drawing_path, require_units="millimeters").passed
    bad = drawings.check_standards(drawing_path, require_units="inches")
    assert not bad.passed
    assert any(f.rule == "units" for f in bad.findings)


def test_find_text_searches_entities_and_attributes(drawing_path):
    assert [h["text"] for h in drawings.find_text(drawing_path, "rev b")] == ["REV B"]
    hits = drawings.find_text(drawing_path, "cci-2088")
    assert len(hits) == 1
    assert hits[0]["text"] == "PARTNO=CCI-2088"
    assert drawings.find_text(drawing_path, "nothing here") == []


def test_unreadable_file_raises_a_useful_message(tmp_path):
    junk = tmp_path / "broken.dxf"
    junk.write_text("this is not a dxf file")
    with pytest.raises(ValueError) as exc:
        drawings.summarize(junk)
    assert "broken.dxf" in str(exc.value)
