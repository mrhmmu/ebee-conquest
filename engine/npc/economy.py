from ..economy import canrecruittroops, getendturneconomydelta, getrecruitcosts

# NPC ECONOMY PLANNER 
# economy aspects of npc behavior, such as recruiting troops and managing gold and population
class NpcEconomyPlanner:
    def __init__(
        self,
        provincemap,
        economyconfig,
        countryindex,
        actionwriter,
        npcrecruitslotsperturn,
        npcrecruitgoldcostmultiplier,
        npcrecruitpopulationcostmultiplier,
        npcstategoldbonusperextrastate,
        npcstatepopulationbonusperextrastate,
    ):
        self.provincemap = provincemap if provincemap is not None else {}
        self.economyconfig = economyconfig
        self.countryindex = countryindex
        self.actionwriter = actionwriter
        self.npcrecruitslotsperturn = npcrecruitslotsperturn
        self.npcrecruitgoldcostmultiplier = npcrecruitgoldcostmultiplier
        self.npcrecruitpopulationcostmultiplier = npcrecruitpopulationcostmultiplier
        self.npcstategoldbonusperextrastate = npcstategoldbonusperextrastate
        self.npcstatepopulationbonusperextrastate = npcstatepopulationbonusperextrastate

    def initializecountryeconomy(self, countryeconomy):
        startinggold = int(self.economyconfig.get("startinggold", 0))
        startingpopulation = int(self.economyconfig.get("startingpopulation", 0))
        startingstability = float(self.economyconfig.get("startingstability", 50.0))
        startingpp = int(self.economyconfig.get("startingpp", 200))
        startingap = int(self.economyconfig.get("startingap", 100))

        for countryname in self.countryindex.allcountries():
            if countryname not in countryeconomy:
                countryeconomy[countryname] = {
                    "gold": startinggold,
                    "population": startingpopulation,
                    "stability": startingstability,
                    "pp": startingpp,
                    "ap": startingap,
                }

    def countcontrolledstates(self, controlledprovinceids):
        return self.countryindex.countcontrolledstates(controlledprovinceids)

    def applycountryeconomy(self, countryeconomy, countryname, controlledprovinceids, personality=None):
        _ = personality
        economystate = countryeconomy.get(countryname)
        if not economystate:
            return

        controlledprovincecount = len(controlledprovinceids)
        goldincome, populationgrowth, stabilitydelta, ppincome, apincome = getendturneconomydelta(
            controlledprovincecount,
            economyconfig=self.economyconfig,
        )

        controlledstatecount = self.countcontrolledstates(controlledprovinceids)
        extracontrolledstates = max(0, controlledstatecount - 1)
        goldincome += extracontrolledstates * self.npcstategoldbonusperextrastate
        populationgrowth += extracontrolledstates * self.npcstatepopulationbonusperextrastate

        economystate["gold"] += goldincome
        economystate["population"] += populationgrowth
        economystate["stability"] = max(0.0, min(100.0, economystate.get("stability", 50.0) + stabilitydelta))
        economystate["pp"] = economystate.get("pp", 0) + ppincome
        economystate["ap"] = economystate.get("ap", 0) + apincome

    def pickrecruitprovinceids(self, countryname, warlookup, maxcount=1, personality=None):
        _ = personality
        if maxcount <= 0:
            return []

        coreprovinceids = self.countryindex.corecontrolledprovinceids(countryname)
        if not coreprovinceids:
            return []
        coreprovinceidset = set(coreprovinceids)

        warenemyset = set(warlookup.get(countryname, set()))
        if warenemyset:
            frontlinecoreprovinceids = [
                provinceid
                for provinceid in sorted(self.countryindex.frontlineprovinceids(countryname, warenemyset))
                if provinceid in coreprovinceidset
            ]
            candidateprovinceids = frontlinecoreprovinceids if frontlinecoreprovinceids else coreprovinceids
        else:
            peacebordercoreprovinceids = [
                provinceid
                for provinceid in sorted(self.countryindex.frontlineprovinceids(countryname))
                if provinceid in coreprovinceidset
            ]
            candidateprovinceids = peacebordercoreprovinceids if peacebordercoreprovinceids else coreprovinceids

        candidateprovinceids = sorted(
            candidateprovinceids,
            key=lambda provinceid: (
                int(self.provincemap[provinceid].get("troops", 0)),
                provinceid,
            ),
        )
        return candidateprovinceids[:maxcount]

    def pickrecruitprovince(self, countryname, warlookup, personality=None):
        targetprovinceids = self.pickrecruitprovinceids(
            countryname,
            warlookup,
            maxcount=1,
            personality=personality,
        )
        if not targetprovinceids:
            return None

        return targetprovinceids[0]

    def recruitslotlimit(self, personality=None):
        priority = getattr(personality, "recruitmentpriority", 1.0) if personality else 1.0
        return max(1, int(self.npcrecruitslotsperturn * priority))


    # TODO: add more complex recruitment logic here, such as prioritizing provinces with lower troop counts or those closer to the frontlines, or adjusting recruitment based on personality traits or current war status.
    # THIS IS FOR RECRUITING TROOPS, NOT MOVING THEM - MOVEMENT LOGIC SHOULD GO IN NPCDEFENSEPLANNER OR NPCINVASIONPLANNER
    def recruittroops(self, countryeconomy, countryname, warlookup, turnnumber, personality=None):
        slotlimit = self.recruitslotlimit(personality=personality)
        targetprovinceids = self.pickrecruitprovinceids(
            countryname,
            warlookup,
            maxcount=slotlimit,
            personality=personality,
        )
        if not targetprovinceids:
            return False

        economystate = countryeconomy.get(countryname)
        if not economystate:
            return False

        recruitamount = int(self.economyconfig.get("recruitamount", 100))
        recruitgoldcostperunit = int(self.economyconfig.get("recruitgoldcostperunit", 1))
        recruitpopulationcostperunit = int(self.economyconfig.get("recruitpopulationcostperunit", 1))
        recruitslotcount = max(1, min(len(targetprovinceids), int(slotlimit)))
        perprovincebase = recruitamount // recruitslotcount
        remainder = recruitamount % recruitslotcount

        recruitedany = False
        for recruitindex, targetprovinceid in enumerate(targetprovinceids[:recruitslotcount]):
            provinceamount = perprovincebase + (1 if recruitindex < remainder else 0)
            if provinceamount <= 0:
                continue

            basegoldcost, basepopulationcost = getrecruitcosts(
                provinceamount,
                recruitgoldcostperunit,
                recruitpopulationcostperunit,
            )
            requiredgold = max(1, int(round(basegoldcost * self.npcrecruitgoldcostmultiplier)))
            requiredpopulation = max(1, int(round(basepopulationcost * self.npcrecruitpopulationcostmultiplier)))

            if not canrecruittroops(
                economystate.get("gold", 0),
                economystate.get("population", 0),
                requiredgold,
                requiredpopulation,
            ):
                continue

            self.actionwriter.recruit(countryname, targetprovinceid, provinceamount, turnnumber)
            economystate["gold"] -= requiredgold
            economystate["population"] -= requiredpopulation
            recruitedany = True

        return recruitedany
