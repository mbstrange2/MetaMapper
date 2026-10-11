import json
import os

# CGRA data word width in bits: the lake spec's data_width.
# - The compile flow (`aha map` -> scripts/map_app.py) takes it from the spec's lake
#   collateral, LAKE_COLLATERAL_JSON_MEM (the file clockwork reads).
# - garnet, which builds the fabric from the spec, calls set_data_width() before mapping.
# 16 without either. Read it with data_width() at use time (not at import), so a
# set_data_width() from garnet applies everywhere.
_data_width = None


def set_data_width(width):
    global _data_width
    _data_width = int(width)


def data_width():
    global _data_width
    if _data_width is None:
        path = os.environ.get("LAKE_COLLATERAL_JSON_MEM", "")
        width = 16
        if path:
            with open(path) as f:
                width = int(json.load(f).get("data_width", 16))
        _data_width = width
    return _data_width


def __getattr__(name):
    # Compatibility: older callers (e.g. garnet copies predating set_data_width) import
    # DATA_WIDTH; resolve it at their import time instead of at this module's.
    if name == "DATA_WIDTH":
        return data_width()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
