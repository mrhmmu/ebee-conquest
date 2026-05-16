from dataclasses import dataclass
from typing import Any, Mapping

from .focuseffects import FocusEffectContext, FocusEffectRegistry, createeffectregistry


@dataclass(frozen=True)
class Focus:
    id: str
    title: str
    description: str = ""
    turncount: int = 1
    prerequisites: tuple[str, ...] = ()
    mutuallyexclusive: tuple[str, ...] = ()
    effects: tuple[Mapping[str, Any], ...] = ()
    icon: str = ""
    x: int = 0
    y: int = 0

    @classmethod
    def fromdata(cls, data: Mapping[str, Any]):
        focusid = str(data.get("id", "")).strip()
        if not focusid:
            raise ValueError("fail!! id canot be empty")

        title = str(data.get("title", focusid)).strip() or focusid
        description = str(data.get("description", "")).strip()
        turncount = max(1, int(data.get("turns", data.get("turns_required", 1)) or 1))
        prerequisites = tuple(str(item).strip() for item in data.get("prerequisites", ()) if str(item).strip())
        mutuallyexclusive = tuple(
            str(item).strip() for item in data.get("mutually_exclusive", ()) if str(item).strip()
        )
        effects = tuple(dict(effect) for effect in data.get("effects", ()) if isinstance(effect, Mapping))
        icon = str(data.get("icon", "")).strip()

        position = data.get("position", {})
        if isinstance(position, Mapping):
            defaultx = position.get("x", 0)
            defaulty = position.get("y", 0)
        else:
            defaultx = 0
            defaulty = 0

        return cls(
            id=focusid,
            title=title,
            description=description,
            turncount=turncount,
            prerequisites=prerequisites,
            mutuallyexclusive=mutuallyexclusive,
            effects=effects,
            icon=icon,
            x=int(data.get("x", defaultx) or 0),
            y=int(data.get("y", defaulty) or 0),
        )


@dataclass(frozen=True)
class FocusStartResult:
    success: bool
    focusid: str | None = None
    reason: str = ""

# @dataclass(frozen=True)
@dataclass(frozen=True)
class FocusAdvanceResult:
    activefocusid: str | None = None
    completedfocusid: str | None = None
    turnsspent: int = 0
    turnsrequired: int = 0
    appliedeffects: tuple[Mapping[str, Any], ...] = ()
    message: str = ""


class FocusTree:
    def __init__(
        self,
        treeid: str,
        country: str | None,
        name: str,
        focuses,
        effectregistry: FocusEffectRegistry | None = None,
    ):
        self.treeid = str(treeid or "focus_tree")
        self.country = country
        self.name = str(name or self.treeid)
        self.focuses: dict[str, Focus] = {focus.id: focus for focus in focuses}
        self.completedids: set[str] = set()
        self.activeid: str | None = None
        self.activeturns = 0
        self.progress: dict[str, int] = {}
        self.lastmessage = ""
        self.effectregistry = effectregistry or createeffectregistry()
        self.exclusives = self.buildexclusives()
        self.validate()





#@dataclass(frozen=True)


    # create empty focus tree with no focus
    @classmethod
    def empty(cls, country: str | None = None):
        name = f"{country} National Policy" if country else "National Policy"
        return cls("empty", country, name, ())





    def buildexclusives(self):
        exclusives = {focusid: set() for focusid in self.focuses}
        for focus in self.focuses.values():
            for otherid in focus.mutuallyexclusive:
                exclusives.setdefault(focus.id, set()).add(otherid)
                exclusives.setdefault(otherid, set()).add(focus.id)
        return exclusives




    # check for prerequisite
    def validate(self):
        focusids = set(self.focuses)
        for focus in self.focuses.values():
            missingprerequisites = set(focus.prerequisites) - focusids
            if missingprerequisites:
                missing = ", ".join(sorted(missingprerequisites))
                raise ValueError(f"Focus '{focus.id}' references unknown prerequisites: {missing}")

            missingexclusive = set(focus.mutuallyexclusive) - focusids
            if missingexclusive:
                missing = ", ".join(sorted(missingexclusive))
                raise ValueError(f"Focus '{focus.id}' references unknown mutually exclusive focuses: {missing}")


    # focus start
    def startfocus(self, focusid: str):
        focus = self.focuses.get(str(focusid or "").strip())
        if focus is None:
            return self.startresult(False, None, "Focus does not exist.")

        canstart, reason = self.canstartfocus(focus.id)
        if not canstart:
            return self.startresult(False, focus.id, reason)
        # print("start focus", focus.id)



        self.activeid = focus.id
        self.activeturns = self.progress.get(focus.id, 0)
        return self.startresult(True, focus.id, f"Started focus: {focus.title}")



    def advanceturn(self, context: FocusEffectContext | None = None):
        if self.activeid is None:
            return FocusAdvanceResult(message="No active focus.")


        focus = self.focuses[self.activeid]
        self.activeturns += 1
        self.progress[focus.id] = min(self.activeturns, focus.turncount)



        if self.activeturns < focus.turncount:
            remaining = focus.turncount - self.activeturns
            self.lastmessage = f"{focus.title}: {remaining} turn(s) remaining."
            return FocusAdvanceResult(
                activefocusid=focus.id,
                turnsspent=self.activeturns,
                turnsrequired=focus.turncount,
                message=self.lastmessage,
            )


        appliedeffects = ()
        if context is not None:
            appliedeffects = tuple(self.effectregistry.apply(focus.effects, context))

        self.completedids.add(focus.id)
        self.progress[focus.id] = focus.turncount
        self.activeid = None
        self.activeturns = 0
        self.lastmessage = f"Completed focus: {focus.title}"

        return FocusAdvanceResult(
            completedfocusid=focus.id,
            turnsspent=focus.turncount,
            turnsrequired=focus.turncount,
            appliedeffects=appliedeffects,
            message=self.lastmessage,
        )






    def canstartfocus(self, focusid: str):
        focus = self.focuses.get(focusid)
        if focus is None:
            return False, "Focus does not exist"
        if focus.id in self.completedids:
            return False, "Focus already CONMPLETED!."
        if self.activeid is not None:
            activefocus = self.focuses.get(self.activeid)
            activetitle = activefocus.title if activefocus else self.activeid
            return False, f"Another focus is ACTIVE: {activetitle}"

        missing = self.missingprerequisites(focus.id)
        if missing:
            return False, "MISSING prerequisites: " + ", ".join(missing)


        blocked = self.completedexclusivefocuses(focus.id)
        if blocked:
            return False, "BLOCKED by mutually exclusive focus: " + ", ".join(blocked)



        return True, ""



    #check for missing prerequisites
    def missingprerequisites(self, focusid: str):
        focus = self.focuses.get(focusid)
        if focus is None:
            return ()
        return tuple(prerequisite for prerequisite in focus.prerequisites if prerequisite not in self.completedids)

    def completedexclusivefocuses(self, focusid: str):
        blocked = self.exclusives.get(focusid, set()) & self.completedids
        return tuple(sorted(blocked))



    # view data for the ui
    def viewdata(self):
        focusviews = []
        for focus in self.focuses.values():
            canstart, reason = self.canstartfocus(focus.id)
            progress = self.progress.get(focus.id, 0)
            status = self.focusstatus(focus.id, canstart)
            focusviews.append(
                {
                    "id": focus.id,
                    "title": focus.title,
                    "description": focus.description,
                    "turnsrequired": focus.turncount,
                    "progress": progress,
                    "remainingturns": max(0, focus.turncount - progress),
                    "prerequisites": list(focus.prerequisites),
                    "mutuallyexclusive": list(self.exclusives.get(focus.id, ())),
                    "effects": [dict(effect) for effect in focus.effects],
                    "icon": focus.icon,
                    "x": focus.x,
                    "y": focus.y,
                    "status": status,
                    "canstart": canstart,
                    "blockingreason": reason,
                }
            )

        activefocus = self.focuses.get(self.activeid) if self.activeid else None
        return {
            "id": self.treeid,
            "country": self.country,
            "name": self.name,
            "focuses": focusviews,
            "activefocusid": self.activeid,
            "activefocustitle": activefocus.title if activefocus else "",
            "activeturns": self.activeturns,
            "completedids": sorted(self.completedids),
            "lastmessage": self.lastmessage,
        }




    def savestate(self):
        return {
            "activefocusid": self.activeid,
            "activeturns": self.activeturns,
            "completedids": sorted(self.completedids),
            "progress": dict(self.progress),
        }
    def loadstate(self, state: Mapping[str, Any] | None):
        if not state:
            return

        completed = set(str(focusid) for focusid in state.get("completedids", ()))
        self.completedids = completed & set(self.focuses)

        progress = {}
        for focusid, amount in dict(state.get("progress", {})).items():
            if focusid in self.focuses:
                progress[focusid] = max(0, int(amount or 0))
        self.progress = progress

        activeid = state.get("activefocusid")
        if activeid in self.focuses and activeid not in self.completedids:
            self.activeid = activeid
            self.activeturns = max(0, int(state.get("activeturns", 0) or 0))
        else:
            self.activeid = None
            self.activeturns = 0







    # determine focus status for the ui
    # this directly links to coloring and availability in the ui, so it is important to keep this logic consistent and not add any additional status types without updating the ui accordingly
    def focusstatus(self, focusid: str, canstart: bool):
        if focusid in self.completedids:
            return "completed"
        if focusid == self.activeid:
            return "active"
        if self.completedexclusivefocuses(focusid):
            return "blocked"
        if self.missingprerequisites(focusid):
            return "locked"
        if canstart:
            return "available"
        return "waiting"

    def startresult(self, success: bool, focusid: str | None, reason: str):
        self.lastmessage = reason
        return FocusStartResult(success=success, focusid=focusid, reason=reason)
