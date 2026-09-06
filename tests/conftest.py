import ezdxf
import pytest


@pytest.fixture
def drawing_path(tmp_path):
    """A small drawing with two placed parts, a note, and an unused layer.

    Built with setup=False: ezdxf's setup adds standard dimension and arrow
    blocks, which would count as block definitions and make the fixture's
    numbers depend on the library's defaults rather than on what we placed.
    """
    doc = ezdxf.new("R2010", setup=False)
    doc.header["$INSUNITS"] = 4  # millimeters

    for name, color in (("FRAME", 1), ("PANEL", 3), ("NOTES", 7), ("UNUSED", 8)):
        doc.layers.add(name, color=color)

    part = doc.blocks.new(name="PART")
    part.add_attdef(tag="PARTNO", insert=(0, 0))
    part.add_attdef(tag="QTY", insert=(0, -1))
    part.add_attdef(tag="MATERIAL", insert=(0, -2))

    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0), dxfattribs={"layer": "FRAME"})
    msp.add_line((0, 0), (0, 50), dxfattribs={"layer": "FRAME"})
    msp.add_circle((50, 25), 5, dxfattribs={"layer": "PANEL"})
    msp.add_text("REV B", dxfattribs={"layer": "NOTES"})

    # add_blockref + add_auto_attribs hangs the ATTRIBs off the INSERT itself.
    # add_auto_blockref would wrap the whole thing in an anonymous block, and the
    # attributes would not be reachable from the modelspace INSERT.
    msp.add_blockref("PART", (0, 0), dxfattribs={"layer": "FRAME"}).add_auto_attribs(
        {"PARTNO": "CCI-1042", "QTY": "4", "MATERIAL": "Oak"}
    )
    msp.add_blockref("PART", (60, 0), dxfattribs={"layer": "PANEL"}).add_auto_attribs(
        {"PARTNO": "CCI-2088", "QTY": "1", "MATERIAL": "Steel"}
    )

    path = tmp_path / "assembly.dxf"
    doc.saveas(str(path))
    return path
