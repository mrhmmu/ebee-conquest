import json
import os
import re
from typing import Mapping

from .focustree import Focus, FocusTree
# PLEASE DO NOT IMPORT ANYTHINGFROM FOCUS UI
# CIRCULAR IMPORT !!!
# actually just dont mess with this file at all! iTS FOCUS TREE LOADER, NOT UI, DONT MESS WITH IT UNLESS YOU KNOW WHAT YOU ARE DOING!!

FOCUSTREEDATADIR = os.path.join(os.path.dirname(__file__), "data", "focus_trees")


def loadfocustree(filepath: str):
    with open(filepath, "r", encoding="utf-8") as fileobject:
        data = json.load(fileobject)
    return focustreefromdata(data)




def focustreefromdata(data: Mapping):
    focuses = [Focus.fromdata(focusdata) for focusdata in data.get("focuses", ())]
    treeid = data.get("id") or slugify(data.get("country")) or "focus_tree"
    country = data.get("country")
    name = data.get("name") or (f"{country} National Policy" if country else str(treeid))
    name = str(name).replace("Focus Tree", "National Policy")
    return FocusTree(treeid=treeid, country=country, name=name, focuses=focuses)


def loadfocustreeforcountry(countryname: str | None, datadir: str | None = None):
    if not countryname:
        return FocusTree.empty(country=None)

    treedir = datadir or FOCUSTREEDATADIR
    filepath = os.path.join(treedir, f"{slugify(countryname)}.json")
    if os.path.isfile(filepath):
        return loadfocustree(filepath)

    return FocusTree.empty(country=countryname)




def slugify(value):
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")
