"""Mapping at the CGRA data width (the lake spec's data_width).

The width comes from the spec's lake collateral (LAKE_COLLATERAL_JSON_MEM) in the
compile flow, or from garnet's set_data_width(); 16 without either.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import metamapper.data_width as dw

REPO = Path(__file__).resolve().parent.parent
# scripts/map_app.py finds lassen's rule files in the sibling checkout
LASSEN = REPO.parent / "lassen"


@pytest.fixture(autouse=True)
def fresh_width(monkeypatch):
    """data_width() caches its first answer; every test starts unresolved."""
    monkeypatch.setattr(dw, "_data_width", None)
    monkeypatch.delenv("LAKE_COLLATERAL_JSON_MEM", raising=False)
    yield
    dw._data_width = None


def _collateral(tmp_path, **fields):
    p = tmp_path / "lake_collateral_mem.json"
    p.write_text(json.dumps(fields))
    return str(p)


def test_default_is_16():
    assert dw.data_width() == 16


@pytest.mark.parametrize("width", (8, 16, 32, 64))
def test_width_from_the_lake_collateral(tmp_path, monkeypatch, width):
    monkeypatch.setenv("LAKE_COLLATERAL_JSON_MEM", _collateral(tmp_path, data_width=width))
    assert dw.data_width() == width


def test_collateral_without_data_width_is_16(tmp_path, monkeypatch):
    monkeypatch.setenv("LAKE_COLLATERAL_JSON_MEM", _collateral(tmp_path, capacity=1024))
    assert dw.data_width() == 16


def test_set_data_width_wins_over_the_collateral(tmp_path, monkeypatch):
    # garnet builds the fabric from the spec and sets its width before mapping
    monkeypatch.setenv("LAKE_COLLATERAL_JSON_MEM", _collateral(tmp_path, data_width=8))
    dw.set_data_width(32)
    assert dw.data_width() == 32


def test_DATA_WIDTH_compat_name(tmp_path, monkeypatch):
    monkeypatch.setenv("LAKE_COLLATERAL_JSON_MEM", _collateral(tmp_path, data_width=64))
    assert dw.DATA_WIDTH == 64
    with pytest.raises(AttributeError):
        dw.NOT_A_NAME


@pytest.mark.parametrize("width", (16, 8, 32, 64))
def test_pe_and_rules_follow_the_width(width):
    from lassen import PE_fc, gen_PE_fc
    from metamapper.map_design_top import pe_and_rules
    dw.set_data_width(width)
    pe, pkg = pe_and_rules()
    if width == 16:
        assert pe is PE_fc and pkg == "rewrite_rules"
    else:
        # the same object garnet uses, so the rules' arch matches the fabric's PE
        assert pe is gen_PE_fc(width) and pkg == f"rewrite_rules_w{width}"


@pytest.mark.parametrize("width", (16, 32))
def test_io_tile_width(width):
    from hwtypes import BitVector
    from peak.family import PyFamily
    from metamapper.io_tiles import IO_fc
    dw.set_data_width(width)
    io = IO_fc.Py()
    assert int(io(BitVector[width]((1 << width) - 1))) == (1 << width) - 1


@pytest.mark.skipif(not (LASSEN / "lassen" / "rewrite_rules_w32").is_dir(),
                    reason="needs the sibling lassen checkout with rewrite_rules_w32")
def test_map_app_maps_a_32_bit_kernel(tmp_path):
    """scripts/map_app.py on a dw32 kernel (tests/sminmax, compiled against a dw32 spec)
    maps onto gen_PE_fc(32): 32-bit data ports and 132-bit instructions."""
    app = tmp_path / "sminmax_compute.json"
    app.write_text((REPO / "tests" / "examples" / "dw32" / "sminmax_compute.json").read_text())
    env = dict(os.environ, LAKE_COLLATERAL_JSON_MEM=_collateral(tmp_path, data_width=32))
    # absolute path: map_app.py locates lassen relative to its own location
    subprocess.run([sys.executable, str(REPO / "scripts" / "map_app.py"), str(app)],
                   cwd=tmp_path, env=env, check=True, capture_output=True)

    mapped = json.loads((tmp_path / "sminmax_compute_mapped.json").read_text())
    insts = [i for mod in mapped["namespaces"]["global"]["modules"].values()
             for i in mod.get("instances", {}).values()]
    assert sum(i.get("modref") == "global.PE" for i in insts) == 4
    const_widths = {i["genargs"]["width"][1] for i in insts if i.get("genref") == "coreir.const"}
    assert const_widths == {132}

    header = json.loads((tmp_path / "lassen_header.json").read_text())
    ports = dict(header["namespaces"]["global"]["modules"]["PE"]["type"][1])
    assert ports["inst"] == ["Array", 132, "BitIn"]
    assert ports["data0"] == ["Array", 32, "BitIn"] and ports["O0"] == ["Array", 32, "Bit"]
