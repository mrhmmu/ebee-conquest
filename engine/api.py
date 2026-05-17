from . import core, movement, camera
from . import eso as esomodule
from . import npc
from .economy import getdefaulteconomyconfig
from .events import EngineEventType, EventBus


def getprovinceatmouse(mouseposition, provincelist, zoomvalue, camerax, cameray, screenrectangle=None):
    # return the province table under mouse position

    
    for province in provincelist:
        provincerectscreen = camera.getscreenrectangle(province["rectangle"], zoomvalue, camerax, cameray)
        if screenrectangle is not None and not provincerectscreen.colliderect(screenrectangle):
            continue
        if not provincerectscreen.collidepoint(mouseposition):
            continue

        for polygon in province["polygons"]:
            polygonrectscreen = camera.getscreenrectangle(polygon["rectangle"], zoomvalue, camerax, cameray)
            if not polygonrectscreen.collidepoint(mouseposition):
                continue

            polygonpointsscreen = camera.getscreenpoints(polygon["points"], zoomvalue, camerax, cameray)
            if len(polygonpointsscreen) >= 3 and core.ispointinsidepolygon(mouseposition, polygonpointsscreen):
                return province

    return None




# please put your functions here
# DO NOT import anything from runtime.py here

class EbeeEngine:

    def __init__(
        self,
        statefilepath="map/states.svg",
        provincefilepath="map/provinces.svg",
        countrydatafilepath="map/countries.json",
    ):
        

        self.statefilepath = statefilepath
        self.provincefilepath = provincefilepath
        self.countrydatafilepath = countrydatafilepath

        self.eventbus = EventBus()

        self.stateshapelist = []
        self.provinceenrichedlist = []
        self.provincemap = {}
        self.provincegraph = {}
        self.statetocountrylookup = {}
        self.countrytocolorlookup = {}

        self.playercountry = None
        self.currentturnnumber = 1
        self.countriesatwarset = set()
        self.warpairset = set()
        self.npcdirector = None
        self.scriptmanager = None
        self.scriptgetresource = None
        self.scriptsetresource = None
        self.scriptgetselectedcountry = None
        self.scriptgetselectedprovince = None
        self.scriptmessagehandler = None
        self.scripteconomy = {}
        self.selectedcountry = None
        self.selectedprovinceid = None
        self._countryaliaslookup = None


    def on(self, eventname, callback):
        
        return self.eventbus.subscribe(eventname, callback) #susbcribe



    def subscribe(self, eventname, callback):
        return self.eventbus.subscribe(eventname, callback) #same 



    def off(self, eventname, callback):
        return self.eventbus.unsubscribe(eventname, callback) # unsubscribe from event



    def unsubscribe(self, eventname, callback):
        return self.eventbus.unsubscribe(eventname, callback) # same thing



    def initscripts(self, folder="scripts", autoload=True, maxcrashes=3):
        from .scriptloader import ScriptManager

        self.scriptmanager = ScriptManager(self, folder=folder, maxcrashes=maxcrashes)
        if autoload:
            self.scriptmanager.loadall()
        return self.scriptmanager


    def bindscripts(
        self,
        getresource=None,
        setresource=None,
        getselectedcountry=None,
        getselectedprovince=None,
        showmessage=None,
    ):
        self.scriptgetresource = getresource
        self.scriptsetresource = setresource
        self.scriptgetselectedcountry = getselectedcountry
        self.scriptgetselectedprovince = getselectedprovince
        self.scriptmessagehandler = showmessage


    def syncscripts(
        self,
        playercountry=None,
        turn=None,
        wars=None,
        warpairs=None,
        npcdirector=None,
        selectedcountry=None,
        selectedprovinceid=None,
    ):
        if playercountry is not None:
            self.playercountry = playercountry
        if turn is not None:
            self.currentturnnumber = max(1, int(turn))
        if wars is not None:
            self.countriesatwarset = set(country for country in wars if country)
        if warpairs is not None:
            self.warpairset = set(pair for pair in warpairs if pair)
        if npcdirector is not None:
            self.npcdirector = npcdirector
        if selectedcountry is not None:
            self.selectedcountry = selectedcountry
        if selectedprovinceid is not None:
            self.selectedprovinceid = selectedprovinceid


    def draw_script_ui(self, surface):
        if self.scriptmanager is not None:
            self.scriptmanager.drawui(surface)


    def handle_script_ui_event(self, event):
        if self.scriptmanager is None:
            return False
        return self.scriptmanager.handleuievent(event)






    def emit(self, eventname, payload):

        self.eventbus.emit(eventname, payload)


    def _invalidatecountrylookup(self):
        self._countryaliaslookup = None


    def _getcountryaliaslookup(self):
        if self._countryaliaslookup is not None:
            return self._countryaliaslookup

        aliaslookup = {}

        def addcountryalias(countryname):
            if not countryname:
                return
            countrytext = str(countryname).strip()
            if not countrytext:
                return
            lowerknown = countrytext.lower()
            if lowerknown not in aliaslookup:
                aliaslookup[lowerknown] = countrytext

        for countryname in self.countrytocolorlookup.keys():
            addcountryalias(countryname)
        for countryname in self.statetocountrylookup.values():
            addcountryalias(countryname)
        for province in self.provincemap.values():
            for key in ("ownercountry", "controllercountry", "country"):
                addcountryalias(province.get(key))

        self._countryaliaslookup = aliaslookup
        return aliaslookup







    def onWarDeclaration(self, callback):

        return self.on(EngineEventType.WARDECLARED, callback) # war declaration event





    def loadworld(self, onprogress=None):


        self.stateshapelist = core.loadsvgshapes(self.statefilepath, onprogress=onprogress)

        if not self.stateshapelist:
            return False



        self.statetocountrylookup, self.countrytocolorlookup = core.loadcountrydata(self.countrydatafilepath)
        allowedstateidset = set(self.statetocountrylookup.keys())
        self.stateshapelist = [stateshape for stateshape in self.stateshapelist if stateshape["id"] in allowedstateidset]
        if not self.stateshapelist:
            return False

        for stateshape in self.stateshapelist:


            statecountry = self.statetocountrylookup.get(stateshape["id"])
            stateshape["ownercountry"] = statecountry
            stateshape["controllercountry"] = statecountry
            stateshape["country"] = statecountry
            stateshape["countrycolor"] = self.countrytocolorlookup.get(statecountry, (85, 85, 85))


        provinceshapelist = core.loadsvgshapes(self.provincefilepath, onprogress=onprogress)
        if not provinceshapelist:
            return False

        provinceshapelist = [
            province
            for province in provinceshapelist
            if core.getparentstateidfromprovinceid(province["id"]) in allowedstateidset
        ]
        if not provinceshapelist:
            return False


        self.provinceenrichedlist = movement.prepareprovincemetadata(provinceshapelist)


        for province in self.provinceenrichedlist:

            provincecountry = self.statetocountrylookup.get(province["parentstateid"])
            province["ownercountry"] = provincecountry
            province["controllercountry"] = provincecountry
            province["country"] = provincecountry
            province["countrycolor"] = self.countrytocolorlookup.get(provincecountry, (85, 85, 85))



        self.provincemap = {province["id"]: province for province in self.provinceenrichedlist}
        self.provincegraph = esomodule.loadprovincegraphcache(self.provincefilepath, allowedstateidset)
        if self.provincegraph is not None:
            cachedprovinceidset = set(self.provincegraph.keys())
            expectedprovinceidset = set(self.provincemap.keys())
            if cachedprovinceidset != expectedprovinceidset:
                self.provincegraph = None
            else:
                for provinceid, neighborids in self.provincegraph.items():
                    if not neighborids.issubset(expectedprovinceidset):
                        self.provincegraph = None
                        break

        if self.provincegraph is None:
            self.provincegraph = movement.buildprovinceadjacencygraph(self.provincemap, onprogress=onprogress)
            if self.provincegraph is not None:
                esomodule.storeprovincegraphcache(self.provincefilepath, self.provincegraph, allowedstateidset)
        
        
        if self.provincegraph is None:
            return False

        groupedsubdivisionlookup = core.groupsubdivisionsbystate(self.provinceenrichedlist, self.stateshapelist)




        for stateshape in self.stateshapelist:


            subdivisionsforstate = groupedsubdivisionlookup.get(stateshape["id"], []);

            for province in subdivisionsforstate:
                
                ownercountry = stateshape.get("ownercountry", stateshape.get("country"));
                controllercountry = stateshape.get("controllercountry", stateshape.get("country"))
                province["ownercountry"] = ownercountry;
                movement.setprovincecontroller(province, controllercountry, stateshape.get("countrycolor", (85, 85, 85)))


            stateshape["subdivisions"] = subdivisionsforstate


        self._invalidatecountrylookup()

        self.emit(
            EngineEventType.WORLDLOADED, # summary
            {
                "stateCount": len(self.stateshapelist),
                "provinceCount": len(self.provincemap),
                "edgeCount": sum(len(neighborset) for neighborset in self.provincegraph.values()) // 2,
            },
        )

        return True





    def declarewar(self, attackercountry, defendercountry):
        attackercountry = self.scriptcountry(attackercountry)
        defendercountry = self.scriptcountry(defendercountry)
        if not attackercountry or not defendercountry or attackercountry == defendercountry:
            return None

        normalizedpair = self._normalizewarpair(attackercountry, defendercountry)
        if normalizedpair is not None:
            self.warpairset.add(normalizedpair)

        if self.playercountry:
            if attackercountry == self.playercountry:
                self.countriesatwarset.add(defendercountry)
            elif defendercountry == self.playercountry:
                self.countriesatwarset.add(attackercountry)

        payload = {
            "attacker": attackercountry,
            "defender": defendercountry,
            "turn": self.currentturnnumber,
        }
        self.emit(EngineEventType.WARDECLARED, payload)
        return payload

    def addgold(self, countryname, amount):
        return self.addcountryresource(countryname, "gold", amount)

    def add_gold(self, countryname, amount):
        return self.addgold(countryname, amount)

    def addpopulation(self, countryname, amount):
        return self.addcountryresource(countryname, "population", amount)

    def add_population(self, countryname, amount):
        return self.addpopulation(countryname, amount)

    def getgold(self, countryname):
        return self.getcountryresource(countryname, "gold")

    def getpopulation(self, countryname):
        return self.getcountryresource(countryname, "population")

    def setgold(self, countryname, amount):
        return self.setcountryresource(countryname, "gold", amount)

    def setpopulation(self, countryname, amount):
        return self.setcountryresource(countryname, "population", amount)

    def addarmy(self, provinceid, amount):
        return self.add_army(provinceid, amount)

    def add_army(self, province_id, amount):
        province = self.provincemap.get(str(province_id or ""))
        if province is None:
            return None

        troopcount = max(0, int(province.get("troops", 0)) + int(amount))
        province["troops"] = troopcount
        if hasattr(movement, "markprovincetroopactivity"):
            movement.markprovincetroopactivity(province, self.currentturnnumber)
        return troopcount

    def set_province_controller(self, province_id, countryname):
        province = self.provincemap.get(str(province_id or ""))
        country = self.scriptcountry(countryname)
        if province is None or not country:
            return None

        countrycolor = self.countrytocolorlookup.get(country, province.get("countrycolor", (85, 85, 85)))
        movement.setprovincecontroller(province, country, countrycolor)
        self._invalidatecountrylookup()
        return self.getprovincedetails(province.get("id"))

    def set_province_owner(self, province_id, countryname):
        province = self.provincemap.get(str(province_id or ""))
        country = self.scriptcountry(countryname)
        if province is None or not country:
            return None

        province["ownercountry"] = country
        province["ownerCountry"] = country
        self._invalidatecountrylookup()
        return self.getprovincedetails(province.get("id"))

    def get_selected_country(self):
        if self.scriptgetselectedcountry is not None:
            country = self.scriptgetselectedcountry()
            if country:
                return self.scriptcountry(country)
        if self.selectedcountry:
            return self.scriptcountry(self.selectedcountry)
        return self.playercountry

    def get_selected_province_id(self):
        if self.scriptgetselectedprovince is not None:
            provinceid = self.scriptgetselectedprovince()
            if provinceid:
                return str(provinceid)
        if self.selectedprovinceid:
            return str(self.selectedprovinceid)
        return None

    def show_script_message(self, text):
        message = str(text or "")
        if self.scriptmessagehandler is not None:
            return self.scriptmessagehandler(message)
        print(f"scriptloader@EbeeEngine:~$ {message}", flush=True)
        return message

    def addcountryresource(self, countryname, resourcename, amount):
        currentvalue = self.getcountryresource(countryname, resourcename)
        return self.setcountryresource(countryname, resourcename, currentvalue + int(amount))

    def getcountryresource(self, countryname, resourcename):
        country = self.scriptcountry(countryname)
        if not country:
            return 0

        key = str(resourcename)
        if self.scriptgetresource is not None:
            value = self.scriptgetresource(country, key)
            if value is not None:
                return max(0, int(value))

        if self.npcdirector is not None:
            economystate = getattr(self.npcdirector, "countryeconomy", {}).get(country)
            if economystate is not None and key in economystate:
                return max(0, int(economystate.get(key, 0)))

        return max(0, int(self.scripteconomy.get(country, {}).get(key, 0)))

    def setcountryresource(self, countryname, resourcename, amount):
        country = self.scriptcountry(countryname)
        if not country:
            return 0

        key = str(resourcename)
        value = max(0, int(amount))

        if self.scriptsetresource is not None:
            handled = self.scriptsetresource(country, key, value)
            if handled:
                return value

        if self.npcdirector is not None:
            economystate = getattr(self.npcdirector, "countryeconomy", {}).get(country)
            if economystate is not None:
                economystate[key] = value
                return value

        self.scripteconomy.setdefault(country, {})[key] = value
        return value

    def scriptcountry(self, countryname):
        if countryname is None:
            return self.playercountry

        countrytext = str(countryname).strip()
        if not countrytext:
            return self.playercountry
        if countrytext.lower() in {"player", "playercountry", "self"}:
            return self.playercountry
        return self._canonicalizecountry(countrytext)

    def setupnpc(self, playercountry=None, economyconfig=None):
        if economyconfig is None:
            economyconfig = getdefaulteconomyconfig()

        self.npcdirector = npc.NpcDirector(
            self.provincemap,
            self.provincegraph,
            countrytocolorlookup=self.countrytocolorlookup,
            emit=self.emit,
            economyconfig=economyconfig,
        )

        if playercountry is not None:
            self.playercountry = playercountry

        self._rebuildplayerwarset()

        self.npcdirector.setplayercountry(self.playercountry)
        self.npcdirector.sync_player_wars(
            self.playercountry,
            self.countriesatwarset,
            warpairset=self.warpairset,
        )
        return self.npcdirector

    def syncnpcwars(self, playercountry=None, countriesatwarset=None, warpairset=None):
        if self.npcdirector is None:
            self.setupnpc(playercountry=playercountry)

        if playercountry is not None:
            self.playercountry = playercountry

        if countriesatwarset is not None:
            self.countriesatwarset = set(country for country in countriesatwarset if country)

            if self.playercountry:
                for enemycountry in self.countriesatwarset:
                    normalizedpair = self._normalizewarpair(self.playercountry, enemycountry)
                    if normalizedpair is not None:
                        self.warpairset.add(normalizedpair)

        if warpairset is not None:
            normalizedwarpairs = set()
            for warpair in warpairset:
                if not isinstance(warpair, (tuple, list)) or len(warpair) != 2:
                    continue
                normalizedpair = self._normalizewarpair(warpair[0], warpair[1])
                if normalizedpair is not None:
                    normalizedwarpairs.add(normalizedpair)
            self.warpairset = normalizedwarpairs

        self._rebuildplayerwarset()

        self.npcdirector.sync_player_wars(
            self.playercountry,
            self.countriesatwarset,
            warpairset=self.warpairset,
        )

    def runnpcturn(self, movementorderlist, developmentmode=False):
        # Keep signature compatibility; NPC behavior ignores development mode.
        _ = developmentmode
        if self.npcdirector is None:
            self.setupnpc(playercountry=self.playercountry)

        self._rebuildplayerwarset()
        self.npcdirector.sync_player_wars(
            self.playercountry,
            self.countriesatwarset,
            warpairset=self.warpairset,
        )
        summary = self.npcdirector.executeturn(
            movementorderlist,
            self.currentturnnumber,
        )
        return summary

    def _normalizewarpair(self, firstcountry, secondcountry):
        if not firstcountry or not secondcountry:
            return None

        first = self._canonicalizecountry(firstcountry)
        second = self._canonicalizecountry(secondcountry)
        if not first or not second or first == second:
            return None
        if first <= second:
            return (first, second)
        return (second, first)

    def _canonicalizecountry(self, countryname):
        if countryname is None:
            return None

        countrytext = str(countryname).strip()
        if not countrytext:
            return None

        aliaslookup = self._getcountryaliaslookup()
        if countrytext.lower() not in aliaslookup:
            self._invalidatecountrylookup()
            aliaslookup = self._getcountryaliaslookup()
        return aliaslookup.get(countrytext.lower(), countrytext)

    def _rebuildplayerwarset(self):
        if not self.playercountry:
            self.countriesatwarset = set()
            return

        playerset = set()
        for firstcountry, secondcountry in self.warpairset:
            if firstcountry == self.playercountry:
                playerset.add(secondcountry)
            elif secondcountry == self.playercountry:
                playerset.add(firstcountry)

        self.countriesatwarset = playerset






    def getcountrydata(self, countryname):
        countryname = self.scriptcountry(countryname)
        if not countryname or not self.provincemap:
            return {}

        ownedprovinceids = []
        controlledprovinceids = []
        ownedstateids = set()
        controlledstateids = set()
        totaltroopscontrolled = 0

        for province in self.provincemap.values():
            provinceid = province.get("id")
            parentstateid = province.get("parentstateid")

            if movement.getprovinceowner(province) == countryname:
                if provinceid:
                    ownedprovinceids.append(provinceid)
                if parentstateid is not None:
                    ownedstateids.add(parentstateid)

            if movement.getprovincecontroller(province) == countryname:
                if provinceid:
                    controlledprovinceids.append(provinceid)
                if parentstateid is not None:
                    controlledstateids.add(parentstateid)
                totaltroopscontrolled += int(province.get("troops", 0))

        return {
            "country": countryname,
            "ownedProvinceCount": len(ownedprovinceids),
            "controlledProvinceCount": len(controlledprovinceids),
            "controlledTroops": totaltroopscontrolled,
            "gold": self.getgold(countryname),
            "population": self.getpopulation(countryname),
            "ownedProvinceIds": sorted(ownedprovinceids),
            "controlledProvinceIds": sorted(controlledprovinceids),
            "ownedStateIds": sorted(ownedstateids),
            "controlledStateIds": sorted(controlledstateids),
            "atWarWith": sorted(self.countriesatwarset),
            "turn": self.currentturnnumber,
        }


    def getprovincedetails(self, provinceid):
        if not provinceid:
            return {}

        province = self.provincemap.get(provinceid)
        if not province:
            return {}

        controllercountry = movement.getprovincecontroller(province)
        ownercountry = movement.getprovinceowner(province)
        parentstateid = province.get("parentid", province.get("parentstateid"))

        return {
            "id": province.get("id"),
            "stateId": parentstateid,
            "terrain": province.get("terrain"),
            "troops": int(province.get("troops", 0)),
            "ownerCountry": ownercountry,
            "controllerCountry": controllercountry,
            "countryColor": province.get("countrycolor"),
            "center": province.get("center"),
        }


    def getstatedetails(self, stateid):
        if not stateid:
            return {}

        state = next((entry for entry in self.stateshapelist if entry.get("id") == stateid), None)
        if not state:
            return {}

        subdivisions = state.get("subdivisions", [])
        provinceids = [province.get("id") for province in subdivisions if province.get("id")]

        totalstatetroops = sum(int(province.get("troops", 0)) for province in subdivisions)
        controllercountries = sorted(
            {
                movement.getprovincecontroller(province)
                for province in subdivisions
                if movement.getprovincecontroller(province) is not None
            }
        )

        return {
            "id": state.get("id"),
            "ownerCountry": state.get("ownercountry", state.get("country")),
            "controllerCountry": state.get("controllercountry", state.get("country")),
            "countryColor": state.get("countrycolor"),
            "provinceCount": len(provinceids),
            "provinceIds": sorted(provinceids),
            "controllerCountries": controllercountries,
            "totalTroops": totalstatetroops,
            "center": (state["rectangle"].centerx, state["rectangle"].centery),
        }


    def getdetailsatmouse(self, mouseposition, zoomvalue, camerax, cameray, screenrectangle=None, provincelist=None):
        province = self.getprovinceatmouse(
            mouseposition,
            zoomvalue,
            camerax,
            cameray,
            screenrectangle=screenrectangle,
            provincelist=provincelist,
        )

        worldx = (mouseposition[0] - camerax) / zoomvalue
        worldy = (mouseposition[1] - cameray) / zoomvalue

        if not province:
            return {
                "mouseScreen": {"x": mouseposition[0], "y": mouseposition[1]},
                "mouseWorld": {"x": worldx, "y": worldy},
                "province": {},
                "state": {},
                "country": {},
            }

        provinceid = province.get("id")
        parentstateid = province.get("parentid", province.get("parentstateid"))
        controllercountry = movement.getprovincecontroller(province)

        return {
            "mouseScreen": {"x": mouseposition[0], "y": mouseposition[1]},
            "mouseWorld": {"x": worldx, "y": worldy},
            "province": self.getprovincedetails(provinceid),
            "state": self.getstatedetails(parentstateid),
            "country": self.getcountrydata(controllercountry) if controllercountry else {},
        }




    def getprovinceatmouse(self, mouseposition, zoomvalue, camerax, cameray, screenrectangle=None, provincelist=None):
        # api for province at mouse location

        activeprovincelist = self.provinceenrichedlist if provincelist is None else provincelist
        return getprovinceatmouse(
            mouseposition,
            activeprovincelist,
            zoomvalue,
            camerax,
            cameray,
            screenrectangle,
        )
