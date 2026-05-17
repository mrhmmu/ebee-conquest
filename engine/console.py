import math
import pygame
from engine.ai import AIProviderError, create_default_manager

clock = pygame.time.Clock()
#dev console will not be included in the final 



def loaddevmodeflag(filepath="dev.txt"):
    try:
        with open(filepath, "r", encoding="utf-8") as fileobject:
            return fileobject.read().strip().lower() == "true"
    except OSError:
        return False


def _cleanconsoleinputtext(textvalue):
    textvalue = textvalue.replace("\x00", "")
    textvalue = textvalue.replace("\r", " ").replace("\n", " ")
    return "".join(character for character in textvalue if character.isprintable())


def _readclipboardtext():
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        rawtext = pygame.scrap.get(pygame.SCRAP_TEXT)
    except (AttributeError, pygame.error):
        rawtext = None

    if rawtext:
        if isinstance(rawtext, bytes):
            for encodingname in ("utf-8", "utf-16-le", "latin-1"):
                try:
                    return _cleanconsoleinputtext(rawtext.decode(encodingname))
                except UnicodeDecodeError:
                    continue
        return _cleanconsoleinputtext(str(rawtext))

    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        try:
            clipboardtext = root.clipboard_get()
        finally:
            root.destroy()
        return _cleanconsoleinputtext(clipboardtext)
    except Exception:
        return ""




def rundevcommand(
    commandline,
    provincemap,
    playercountry,
    countrytocolor,
    fallbackcolor,
    troopbadgelist,
    eventbus=None,
    currentturnnumber=0,
    commandcontext=None,
    aimanager=None,
    aipendingrequests=None,
):
    commandparts = commandline.strip().split() # arguments
    if not commandparts:
        return "empty command"

    commandname = commandparts[0].lower()
    lowercaselookup = {provinceid.lower(): provinceid for provinceid in provincemap.keys()}


    def getprovinceid(rawtext):
        return lowercaselookup.get(rawtext.lower())

    def getowner(province):
        return province.get("ownercountry", province.get("country"))

    def getcontroller(province):
        return province.get("controllercountry", province.get("country"))

    validterrainset = {"plains", "forest", "hills", "mountains", "desert", "swamp", "urban"}

    knowncountrylookup = {}
    for province in provincemap.values():
        for key in ("ownercountry", "controllercountry", "country"):
            countryname = province.get(key)
            if not countryname:
                continue
            countrytext = str(countryname).strip()
            if not countrytext:
                continue
            lowercountry = countrytext.lower()
            if lowercountry not in knowncountrylookup:
                knowncountrylookup[lowercountry] = countrytext

    def resolvecountry(rawtext):
        if rawtext is None:
            return None
        countrytext = str(rawtext).strip()
        if not countrytext:
            return None
        return knowncountrylookup.get(countrytext.lower())

    def normalizewarpair(firstcountry, secondcountry):
        first = resolvecountry(firstcountry)
        second = resolvecountry(secondcountry)
        if not first or not second or first == second:
            return None
        if first <= second:
            return (first, second)
        return (second, first)

    def setsessionvalue(keyname, value):
        if isinstance(commandcontext, dict):
            commandcontext[keyname] = value

    def getsessionvalue(keyname, defaultvalue=None):
        if isinstance(commandcontext, dict):
            return commandcontext.get(keyname, defaultvalue)
        return defaultvalue

    def getaimanager():
        if aimanager is not None:
            return aimanager
        return getsessionvalue("aimanager")

    def getpendingairequests():
        if aipendingrequests is not None:
            return aipendingrequests
        return getsessionvalue("aipendingrequests")

    def applyplayercountry(newplayercountry):
        canonicalcountry = resolvecountry(newplayercountry) if newplayercountry else None
        setsessionvalue("playercountry", canonicalcountry)

        if canonicalcountry:
            setsessionvalue("gamephase", "play")
            setsessionvalue("countriesatwarset", set())
        else:
            setsessionvalue("countriesatwarset", set())

        npcdirector = getsessionvalue("npcdirector")
        if npcdirector is not None:
            npcdirector.setplayercountry(canonicalcountry)
            npcdirector.sync_player_wars(canonicalcountry, getsessionvalue("countriesatwarset", set()), warpairset=getsessionvalue("warpairset", set()))

        return canonicalcountry

    def recomputeplayerwarset(playercountryvalue, warpairsetvalue):
        if not playercountryvalue:
            return set()
        playerset = set()
        for firstcountry, secondcountry in warpairsetvalue:
            if firstcountry == playercountryvalue:
                playerset.add(secondcountry)
            elif secondcountry == playercountryvalue:
                playerset.add(firstcountry)
        return playerset

    def syncevalscope(evalscope, originalsnapshot):
        if not isinstance(commandcontext, dict):
            return

        for keyname, value in evalscope.items():
            if keyname == "context":
                continue
            if keyname in originalsnapshot and originalsnapshot[keyname] == value:
                continue
            commandcontext[keyname] = value

        scopedcontext = evalscope.get("context")
        if isinstance(scopedcontext, dict) and scopedcontext is not commandcontext:
            commandcontext.update(scopedcontext)




    if commandname == "add_troops" and len(commandparts) == 3:
        provinceid = getprovinceid(commandparts[1])
        if provinceid is None:
            return "province not found"
        try:
            amountvalue = max(0, int(commandparts[2]))
        except ValueError:
            return "amount must be int"
        provincemap[provinceid]["troops"] += amountvalue
        return f"ok {provinceid} troops={provincemap[provinceid]['troops']}"




    if commandname == "remove_troops" and len(commandparts) == 3:
        provinceid = getprovinceid(commandparts[1])
        if provinceid is None:
            return "province not found"
        try:
            amountvalue = max(0, int(commandparts[2]))
        except ValueError:
            return "amount must be int"
        provincemap[provinceid]["troops"] = max(0, provincemap[provinceid]["troops"] - amountvalue)
        return f"ok {provinceid} troops={provincemap[provinceid]['troops']}"




    if commandname == "annex" and len(commandparts) == 2:
        if not playercountry:
            return "pick country first"
        provinceid = getprovinceid(commandparts[1])
        if provinceid is None:
            return "province not found"
        provincemap[provinceid]["ownercountry"] = playercountry
        provincemap[provinceid]["controllercountry"] = playercountry
        provincemap[provinceid]["country"] = playercountry
        provincemap[provinceid]["countrycolor"] = countrytocolor.get(playercountry, fallbackcolor)
        setsessionvalue("mapdirty", True)
        return f"ok annexed {provinceid} to {playercountry}"


    if commandname == "set_troops" and len(commandparts) == 3:

        provinceid = getprovinceid(commandparts[1])

        if provinceid is None:
            return "province not found"
        try:
            amountvalue = max(0, int(commandparts[2]))
        except ValueError:
            return "not int"
        

        provincemap[provinceid]["troops"] = amountvalue


        return f"ok {provinceid} troops={provincemap[provinceid]['troops']}"


    if commandname == "set_terrain" and len(commandparts) == 3:
        provinceid = getprovinceid(commandparts[1])

        if provinceid is None:
            return "province not found"
        terrainvalue = commandparts[2].lower().strip()
        if terrainvalue not in validterrainset:
            return f"invalid terrain. use: {', '.join(sorted(validterrainset))}"
        
        
        provincemap[provinceid]["terrain"] = terrainvalue


        return f"ok {provinceid} terrain={terrainvalue}"


    if commandname == "set_owner" and len(commandparts) >= 3:

        provinceid = getprovinceid(commandparts[1])

        if provinceid is None:
            return "province not found"
        newowner = " ".join(commandparts[2:]).strip()
        if not newowner:
            return "owner required"
        

        provincemap[provinceid]["ownercountry"] = newowner
        setsessionvalue("mapdirty", True)


        return f"ok {provinceid} owner={newowner}"


    if commandname == "set_controller" and len(commandparts) >= 3:
        provinceid = getprovinceid(commandparts[1])


        if provinceid is None:
            return "province not found"
        newcontroller = " ".join(commandparts[2:]).strip()
        if not newcontroller:
            return "controller required"
        

        provincemap[provinceid]["controllercountry"] = newcontroller
        provincemap[provinceid]["country"] = newcontroller
        provincemap[provinceid]["countrycolor"] = countrytocolor.get(newcontroller, fallbackcolor)
        setsessionvalue("mapdirty", True)


        return f"ok {provinceid} controller={newcontroller}"


    if commandname == "province" and len(commandparts) == 2:
        provinceid = getprovinceid(commandparts[1])

        if provinceid is None:
            return "province not found"



        province = provincemap[provinceid]
        owner = getowner(province)
        controller = getcontroller(province)
        troops = province.get("troops", 0)
        terrain = province.get("terrain", "plains")



        return f"{provinceid} | owner={owner} controller={controller} troops={troops} terrain={terrain}"




    if commandname == "find" and len(commandparts) >= 2:

        keyword = " ".join(commandparts[1:]).strip().lower()

        if not keyword:
            return "keyword pls"
        matches = [provinceid for provinceid in provincemap.keys() if keyword in provinceid.lower()]
        if not matches:
            return "no matches"
        

        return f"matches({len(matches)}): {', '.join(matches[:12])}" + (" ..." if len(matches) > 12 else "")




    if commandname == "stats" and len(commandparts) == 1:
        totalprovincecount = len(provincemap)
        totaltroops = sum(max(0, int(province.get("troops", 0))) for province in provincemap.values())
        controllercountlookup = {}


        for province in provincemap.values():
            controller = getcontroller(province) or "None"
            controllercountlookup[controller] = controllercountlookup.get(controller, 0) + 1
        topcontrollers = sorted(controllercountlookup.items(),key=lambda item:item[1],reverse=True)[:6]
        topcontrollertext = ", ".join(f"{name}:{count}" for name, count in topcontrollers)



        return f"provinces={totalprovincecount} troops={totaltroops} controllers[{topcontrollertext}]"





    if commandname == "country_stats":
        rawtargetcountry = " ".join(commandparts[1:]).strip() if len(commandparts) >= 2 else ""

        if not rawtargetcountry:
            countrystatslookup = {}
            for province in provincemap.values():
                owner = getowner(province)
                controller = getcontroller(province)
                if owner:
                    countrystatslookup.setdefault(owner, [0, 0, 0])[0] += 1
                if controller:
                    controllerstats = countrystatslookup.setdefault(controller, [0, 0, 0])
                    controllerstats[1] += 1
                    controllerstats[2] += max(0, int(province.get("troops", 0)))

            countrystatlist = [
                (countryname, stats[0], stats[1], stats[2])
                for countryname, stats in countrystatslookup.items()
            ]

            if not countrystatlist:
                return "no countries"

            countrystatlist.sort(key=lambda entry: (-entry[3], entry[0]))
            maxrows = 8
            visibleentries = countrystatlist[:maxrows]
            summarytext = " ; ".join(
                f"{name} owned={owned} controlled={controlled} controlled_troops={troops}"
                for name, owned, controlled, troops in visibleentries
            )
            if len(countrystatlist) > maxrows:
                summarytext += " ; ..."
            return summarytext

        targetcountry = resolvecountry(rawtargetcountry)
        if targetcountry is None:
            return f"unknown country: {rawtargetcountry}"

        ownedcount = 0
        controlledcount = 0
        controlledtroops = 0
        for province in provincemap.values():
            if getowner(province) == targetcountry:
                ownedcount += 1
            if getcontroller(province) == targetcountry:
                controlledcount += 1
                controlledtroops += max(0, int(province.get("troops", 0)))

        return (
            f"{targetcountry} | owned={ownedcount} controlled={controlledcount} controlled_troops={controlledtroops}"
        )


    if commandname == "news" and len(commandparts) >= 2:
        if eventbus is None:
            return "eventbus unavailable"

        
        rawtext = commandline.strip()[len(commandparts[0]):].strip()
        titletext = rawtext
        descriptiontext = "No description."
        if "|" in rawtext:
            left, right = rawtext.split("|", 1)
            titletext = left.strip() or "NEWS UPDATE"
            descriptiontext = right.strip() or "No description."

        eventbus.emit(
            "newspopup",
            {
                "title": titletext,
                "description": descriptiontext,
                "imagekey": "placeholder",
                "priority": 1,
            },
        )
        return f"ok queued news popup: {titletext}"

    if commandname == "collapse" and len(commandparts) >= 2:
        if eventbus is None:
            return "eventbus unavailable"
        countryname = commandparts[1]
        descriptiontext = " ".join(commandparts[2:]).strip()
        if not descriptiontext:
            descriptiontext = f"{countryname} has collapsed."
        eventbus.emit(
            "countrycollapsed",
            {
                "country": countryname,
                "description": descriptiontext,
            },
        )
        return f"queued collapse news for {countryname}"



    if commandname in {"war", "declarewar", "declare_war"}:
        if eventbus is None:
            return "i cant connect to eventbus"

        if len(commandparts) not in {2, 3}:
            return "war [country1] [country2] | declarewar [country]"

        if len(commandparts) == 2:
            attackerraw = getsessionvalue("playercountry", playercountry)
            defenderraw = commandparts[1]
            if not attackerraw:
                return "war [country1] [country2]"
        else:
            attackerraw = commandparts[1]
            defenderraw = commandparts[2]

        attackercountry = resolvecountry(attackerraw)
        if attackercountry is None:
            return f"unknown country: {attackerraw}"

        defendercountry = resolvecountry(defenderraw)
        if defendercountry is None:
            return f"unknown country: {defenderraw}"

        if attackercountry.lower() == defendercountry.lower():
            return "countries must differ"

        normalizedpair = normalizewarpair(attackercountry, defendercountry)
        if normalizedpair is None:
            return "countries must differ"

        warpairset = set(getsessionvalue("warpairset", set()))
        if normalizedpair in warpairset:
            return f"already at war: {attackercountry} vs {defendercountry}"
        warpairset.add(normalizedpair)
        setsessionvalue("warpairset", warpairset)

        sessionplayercountry = getsessionvalue("playercountry", playercountry)
        countriesatwarset = recomputeplayerwarset(sessionplayercountry, warpairset)
        setsessionvalue("countriesatwarset", countriesatwarset)

        npcdirector = getsessionvalue("npcdirector")
        if npcdirector is not None:
            npcdirector.sync_player_wars(sessionplayercountry, countriesatwarset, warpairset=warpairset)

        eventbus.emit(
            "wardeclared",
            {
                "attacker": attackercountry,
                "defender": defendercountry,
                "turn": int(getsessionvalue("currentturnnumber", currentturnnumber)),
                "source": "devconsole",
            },
        )
        return f"ok war declared: {attackercountry} -> {defendercountry}"





    if commandname == "observe" and len(commandparts) == 1:
        applyplayercountry(None)
        return "ok observe mode enabled (player control released to AI)"

    if commandname == "setplayercountry" and len(commandparts) >= 2:
        rawcountry = " ".join(commandparts[1:]).strip()
        if not rawcountry:
            return "usage: setplayercountry [country]"

        canonicalcountry = resolvecountry(rawcountry)
        if canonicalcountry is None:
            return f"unknown country: {rawcountry}"

        applyplayercountry(canonicalcountry)
        return f"ok playercountry={canonicalcountry}"

    if commandname == "declarepeace" and len(commandparts) == 3:
        firstcountry = resolvecountry(commandparts[1])
        secondcountry = resolvecountry(commandparts[2])
        if not firstcountry:
            return f"unknown country: {commandparts[1]}"
        if not secondcountry:
            return f"unknown country: {commandparts[2]}"

        normalizedpair = normalizewarpair(firstcountry, secondcountry)
        if normalizedpair is None:
            return "countries must differ"

        warpairset = set(getsessionvalue("warpairset", set()))
        if normalizedpair not in warpairset:
            return f"no active war: {firstcountry} vs {secondcountry}"

        warpairset.remove(normalizedpair)
        setsessionvalue("warpairset", warpairset)

        sessionplayercountry = getsessionvalue("playercountry", playercountry)
        countriesatwarset = recomputeplayerwarset(sessionplayercountry, warpairset)
        setsessionvalue("countriesatwarset", countriesatwarset)

        npcdirector = getsessionvalue("npcdirector")
        if npcdirector is not None:
            npcdirector.sync_player_wars(sessionplayercountry, countriesatwarset, warpairset=warpairset)

        if eventbus is not None:
            eventbus.emit(
                "warended",
                {
                    "country1": firstcountry,
                    "country2": secondcountry,
                    "turn": int(getsessionvalue("currentturnnumber", currentturnnumber)),
                    "source": "devconsole",
                },
            )
        return f"ok peace declared: {firstcountry} & {secondcountry}"

    if commandname == "takeovercountry" and len(commandparts) == 3:
        sourcecountry = resolvecountry(commandparts[1])
        targetcountry = resolvecountry(commandparts[2])
        if sourcecountry is None:
            return f"unknown country: {commandparts[1]}"
        if targetcountry is None:
            return f"unknown country: {commandparts[2]}"
        if sourcecountry == targetcountry:
            return "countries must differ"

        changedownercount = 0
        changedcontrollercount = 0
        for province in provincemap.values():
            if getowner(province) == sourcecountry:
                province["ownercountry"] = targetcountry
                changedownercount += 1
            if getcontroller(province) == sourcecountry:
                province["controllercountry"] = targetcountry
                province["country"] = targetcountry
                province["countrycolor"] = countrytocolor.get(targetcountry, fallbackcolor)
                changedcontrollercount += 1
        if changedownercount or changedcontrollercount:
            setsessionvalue("mapdirty", True)

        npcdirector = getsessionvalue("npcdirector")
        if npcdirector is not None:
            npcdirector.rebuildcountryindexes()
            npcdirector._initializecountryeconomy()

        sessionplayercountry = getsessionvalue("playercountry", playercountry)
        if sessionplayercountry == sourcecountry:
            setsessionvalue("playercountry", targetcountry)

        return (
            f"ok takeover {sourcecountry} -> {targetcountry} "
            f"(owner={changedownercount} controller={changedcontrollercount})"
        )

    if commandname == "spawnwar" and len(commandparts) == 2:
        sourcecountry = resolvecountry(commandparts[1])
        if sourcecountry is None:
            return f"unknown country: {commandparts[1]}"

        targetcountryset = set()
        provincegraph = getsessionvalue("provincegraph")
        if provincegraph:
            for provinceid, province in provincemap.items():
                if getcontroller(province) != sourcecountry:
                    continue
                for neighborid in provincegraph.get(provinceid, ()): 
                    neighborprovince = provincemap.get(neighborid)
                    if not neighborprovince:
                        continue
                    neighborcountry = getcontroller(neighborprovince)
                    if neighborcountry and neighborcountry != sourcecountry:
                        targetcountryset.add(neighborcountry)

        if not targetcountryset:
            targetcountryset = {
                countryname
                for countryname in knowncountrylookup.values()
                if countryname != sourcecountry
            }

        if not targetcountryset:
            return f"no targets found for {sourcecountry}"

        warpairset = set(getsessionvalue("warpairset", set()))
        createdpairs = []
        for targetcountry in sorted(targetcountryset):
            normalizedpair = normalizewarpair(sourcecountry, targetcountry)
            if normalizedpair is None or normalizedpair in warpairset:
                continue
            warpairset.add(normalizedpair)
            createdpairs.append((sourcecountry, targetcountry))
            if eventbus is not None:
                eventbus.emit(
                    "wardeclared",
                    {
                        "attacker": sourcecountry,
                        "defender": targetcountry,
                        "turn": int(getsessionvalue("currentturnnumber", currentturnnumber)),
                        "source": "devconsole",
                    },
                )

        setsessionvalue("warpairset", warpairset)
        sessionplayercountry = getsessionvalue("playercountry", playercountry)
        countriesatwarset = recomputeplayerwarset(sessionplayercountry, warpairset)
        setsessionvalue("countriesatwarset", countriesatwarset)

        npcdirector = getsessionvalue("npcdirector")
        if npcdirector is not None:
            npcdirector.sync_player_wars(sessionplayercountry, countriesatwarset, warpairset=warpairset)

        if not createdpairs:
            return f"no new wars created for {sourcecountry}"
        targettext = ", ".join(pair[1] for pair in createdpairs)
        return f"ok spawned wars: {sourcecountry} vs {targettext}"

    if commandname == "economy":
        if len(commandparts) == 1:
            currentgold = int(getsessionvalue("playergold", 0))
            currentpopulation = int(getsessionvalue("playerpopulation", 0))
            return f"economy player gold={currentgold} population={currentpopulation}"

        npcdirector = getsessionvalue("npcdirector")

        if len(commandparts) == 2 and commandparts[1].lower() == "player":
            currentgold = int(getsessionvalue("playergold", 0))
            currentpopulation = int(getsessionvalue("playerpopulation", 0))
            return f"economy player gold={currentgold} population={currentpopulation}"

        if len(commandparts) == 4 and commandparts[1].lower() in {"set", "add"}:
            actionname = commandparts[1].lower()
            statname = commandparts[2].lower()
            if statname not in {"gold", "population"}:
                return "usage: economy [set|add] [gold|population] [value]"
            try:
                amountvalue = int(commandparts[3])
            except ValueError:
                return "value must be int"

            sessionkey = "playergold" if statname == "gold" else "playerpopulation"
            currentvalue = int(getsessionvalue(sessionkey, 0))
            if actionname == "set":
                nextvalue = max(0, amountvalue)
            else:
                nextvalue = max(0, currentvalue + amountvalue)
            setsessionvalue(sessionkey, nextvalue)
            return f"ok player {statname}={nextvalue}"

        if len(commandparts) >= 5 and commandparts[1].lower() == "country":
            if npcdirector is None:
                return "npcdirector unavailable"

            rawcountry = commandparts[2]
            canonicalcountry = getattr(npcdirector, "_canonicalizecountry", lambda value: value)(rawcountry)
            if not canonicalcountry:
                return f"unknown country: {rawcountry}"

            actionname = commandparts[3].lower()
            statname = commandparts[4].lower()
            if actionname not in {"set", "add"}:
                return "usage: economy country [country] [set|add] [gold|population] [value]"
            if statname not in {"gold", "population"}:
                return "usage: economy country [country] [set|add] [gold|population] [value]"
            if len(commandparts) != 6:
                return "usage: economy country [country] [set|add] [gold|population] [value]"
            try:
                amountvalue = int(commandparts[5])
            except ValueError:
                return "value must be int"

            if canonicalcountry not in npcdirector.countryeconomy:
                npcdirector._initializecountryeconomy()
            if canonicalcountry not in npcdirector.countryeconomy:
                return f"unknown country: {rawcountry}"

            currentvalue = int(npcdirector.countryeconomy[canonicalcountry].get(statname, 0))
            if actionname == "set":
                nextvalue = max(0, amountvalue)
            else:
                nextvalue = max(0, currentvalue + amountvalue)
            npcdirector.countryeconomy[canonicalcountry][statname] = nextvalue
            return f"ok economy {canonicalcountry} {statname}={nextvalue}"

        return (
            "usage: economy | economy player | economy [set|add] [gold|population] [value] | "
            "economy country [country] [set|add] [gold|population] [value]"
        )
    

    if commandname == "exit" and len(commandparts) == 1:
        manager = getaimanager()
        if manager is not None and hasattr(manager, "shutdown"):
            manager.shutdown(wait=False)
        pygame.quit()
        exit(0)

    if commandname == "aikey":
        if len(commandparts) != 2:
            return "usage: aikey [DeepSeek API key]"
        manager = getaimanager()
        if manager is None:
            return "ai manager unavailable"
        try:
            manager.set_provider_config("deepseek", api_key=commandparts[1])
        except Exception as error:
            return f"ai key error: {error}"
        return "ok DeepSeek API key set"

    if commandname == "ai":
        prompt = commandline.strip()[len(commandparts[0]):].strip()
        if not prompt:
            return "usage: ai [prompt]"
        manager = getaimanager()
        if manager is None:
            return "ai manager unavailable"
        pendingrequests = getpendingairequests()
        if pendingrequests is None:
            return "ai async queue unavailable"
        if not hasattr(manager, "ask_async"):
            return "ai manager does not support async requests"
        try:
            request = manager.ask_async(prompt)
            pendingrequests.append(request)
            return f"ai request #{request.request_id} sent to {request.provider_name}"
        except AIProviderError as error:
            return f"ai error: {error}"
        except Exception as error:
            return f"ai error: {error}"



    if commandname in {"evaluate", "eval"} and len(commandparts) >= 2:
        coderaw = commandline.strip()[len(commandparts[0]):].strip()
        try:
            safebuiltins = {
                "abs": abs,
                "all": all,
                "any": any,
                "bool": bool,
                "dict": dict,
                "float": float,
                "int": int,
                "len": len,
                "list": list,
                "max": max,
                "min": min,
                "pow": pow,
                "range": range,
                "round": round,
                "set": set,
                "sorted": sorted,
                "str": str,
                "sum": sum,
                "tuple": tuple,
                "print": print,
            }

            evalscope = {
                "provincemap": provincemap,
                "playercountry": getsessionvalue("playercountry", playercountry),
                "countrytocolor": countrytocolor,
                "fallbackcolor": fallbackcolor,
                "troopbadgelist": troopbadgelist,
                "eventbus": eventbus,
                "currentturnnumber": currentturnnumber,
                "math": math,
                "context": commandcontext,
            }

            if isinstance(commandcontext, dict):
                for keyname, value in commandcontext.items():
                    if keyname not in evalscope:
                        evalscope[keyname] = value

            originalsnapshot = dict(commandcontext) if isinstance(commandcontext, dict) else {}

            trymode = "eval"
            if coderaw.startswith("exec "):
                trymode = "exec"
                coderaw = coderaw[5:].lstrip()
            elif "\n" in coderaw or ";" in coderaw:
                trymode = "exec"

            if trymode == "eval":
                result = eval(coderaw, {"__builtins__": safebuiltins}, evalscope)
                syncevalscope(evalscope, originalsnapshot)
                return f"eval result: {result!r}"

            exec(coderaw, {"__builtins__": safebuiltins}, evalscope)
            syncevalscope(evalscope, originalsnapshot)
            if "_" in evalscope:
                return f"exec ok: _={evalscope['_']!r}"
            return "exec ok"
        except Exception as error:
            return f"eval error: {error}"

    if commandname == "help:debug" and len(commandparts) == 1:
        return (
            "debug: province [id], find [text], stats, country_stats [country], "
            "set_troops [id] [n], set_terrain [id] [terrain], set_owner [id] [country], set_controller [id] [country], "
            "eval [code], observe, setplayercountry [country], economy, ai [prompt], aikey [KEY], "
            "war [country1] [country2], declarewar [country], declarepeace [country1] [country2], "
            "takeovercountry [from] [to], spawnwar [country]"
        )

    if commandname == "help" and len(commandparts) == 1:
        return (
            "commands: add_troops [province] [amount], remove_troops [province] [amount], annex [province], "
            "province [id], find [text], stats, country_stats [country], news [title | description], "
            "collapse [country] [description], war [country1] [country2], declarewar [country], "
            "observe, setplayercountry [country], "
            "economy, eval [code], ai [prompt], aikey [KEY], declarepeace [country1] [country2], "
            "takeovercountry [from] [to], spawnwar [country], help:debug, help, exit"
        )



    return "what??"




class developmentconsole:
    # in game console

    #init is the only time we can load the dev mode flag

    def __init__(self, enabled, aimanager=None):
        self.enabled = enabled
        self.visible = False
        self.inputtext = ""
        self.loglines = ["dev console ready"]
        self.buttonrectangle = None
        self.panelrectangle = None
        self.closerectangle = None
        self.aimanager = aimanager or create_default_manager()
        self.aipendingrequests = []

    def collectairesponses(self):
        if not self.aipendingrequests:
            return

        pendingrequests = []
        for request in self.aipendingrequests:
            if not request.done():
                pendingrequests.append(request)
                continue

            try:
                response = request.result()
            except AIProviderError as error:
                self.loglines.append(f"ai #{request.request_id} error: {error}")
            except Exception as error:
                self.loglines.append(f"ai #{request.request_id} error: {error}")
            else:
                responsetext = response.strip() if isinstance(response, str) else str(response).strip()
                if not responsetext:
                    responsetext = "[empty response]"
                self.loglines.append(f"ai #{request.request_id}: {responsetext}")

        self.aipendingrequests = pendingrequests


    def drawbutton(self, screen, rectangle, textvalue, fontobject, enabled=True, pulse=False):
        if enabled:
            basecolor = (255, 20, 90) #blue
            if pulse:
                timer = pygame.time.get_ticks() * 0.008
                glowamount = 0.2 + 0.35 * (0.5 + 0.5 * math.sin(timer))
                basecolor = (
                    int(basecolor[0] + (255 - basecolor[0]) * glowamount),
                    int(basecolor[1] + (255 - basecolor[1]) * glowamount),
                    int(basecolor[2] + (255 - basecolor[2]) * glowamount),
                )
        else:
            basecolor = (70, 70, 70)#gray

        pygame.draw.rect(screen, basecolor, rectangle, border_radius=1)
        pygame.draw.rect(screen, (35, 35, 35), rectangle, width=1, border_radius=1) #dark border
        textcolor = (240, 240, 240) if enabled else (145, 145, 145) # light if enabled dark if not
        labelsurface = fontobject.render(textvalue, True, textcolor)
        screen.blit(labelsurface, labelsurface.get_rect(center=rectangle.center))



    def wraptext(self, text, font, maxwidth):

        # fix clip
        words = text.split()
        lines = []
        current = []

        for word in words:
            test = " ".join(current + [word])
            if font.size(test)[0] <= maxwidth:
                current.append(word)
            else:
                lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))

        return lines
    # the gui render code 
    #TODO: move this to gui.py

    def draw(self, screen, fontobject, smallfontobject,clock, text):
        if not self.enabled:
            self.buttonrectangle = None
            self.panelrectangle = None
            self.closerectangle = None
            return

        self.collectairesponses()

        windowwidth, windowheight = screen.get_size()
        self.buttonrectangle = None

        if not self.visible:
            self.panelrectangle = None
            self.closerectangle = None
            return

        self.panelrectangle = pygame.Rect(
            int(windowwidth * 0.14),
            int(windowheight * 0.14),
            int(windowwidth * 0.72),
            int(windowheight * 0.72),
        )
        #window
        pygame.draw.rect(screen, (18, 18, 18), self.panelrectangle, border_radius=1)
        pygame.draw.rect(screen, (120, 120, 120), self.panelrectangle, width=1, border_radius=1)

        titletext = fontobject.render("dev console", True, (240, 240, 240))
        screen.blit(titletext, (self.panelrectangle.x + 12, self.panelrectangle.y + 10))

        self.closerectangle = pygame.Rect(self.panelrectangle.right - 76, self.panelrectangle.y + 8, 64, 24)
        self.drawbutton(screen, self.closerectangle, "close", smallfontobject, enabled=True)

        logviewrectangle = pygame.Rect(
            self.panelrectangle.x + 12,
            self.panelrectangle.y + 42,
            self.panelrectangle.width - 24,
            self.panelrectangle.height - 94,
        )


        pygame.draw.rect(screen, (10, 10, 10), logviewrectangle)
        pygame.draw.rect(screen, (70, 70, 70), logviewrectangle, width=1)


        lineheight = 16
        maxtextwidth = logviewrectangle.width - 12
        wrapped = []

        for linevalue in self.loglines:
            wrapped.extend(self.wraptext(linevalue, smallfontobject, maxtextwidth))

        maxrows = max(1, (logviewrectangle.height - 8) // lineheight)
        visiblelines = wrapped[-maxrows:]


        #render to console
        for rowindex, linevalue in enumerate(visiblelines):
            linesurface = smallfontobject.render(linevalue, True, (180, 220, 180))
            screen.blit(linesurface, (logviewrectangle.x + 6, logviewrectangle.y + 4 + rowindex * lineheight))


        # maxrows = max(1, (logviewrectangle.height - 8) // 16)
        # visiblelines = self.loglines[-maxrows:]


        # #TO render log line into cosole
        # for rowindex, linevalue in enumerate(visiblelines):
        #     linesurface = smallfontobject.render(linevalue, True, (180, 220, 180))
        #     screen.blit(linesurface, (logviewrectangle.x + 6, logviewrectangle.y + 4 + rowindex * 16))



        inputrectangle = pygame.Rect(
            self.panelrectangle.x + 12,
            self.panelrectangle.bottom - 42,
            self.panelrectangle.width - 24,
            30,
        )


        pygame.draw.rect(screen, (22, 22, 22), inputrectangle)
        pygame.draw.rect(screen, (110, 110, 110), inputrectangle, width=1)
        inputsurface = smallfontobject.render("> " + self.inputtext, True, (230, 230, 230))
        screen.blit(inputsurface, (inputrectangle.x + 6, inputrectangle.y + 8))


    def handleleftclick(self, mouseposition):
        if not self.enabled:
            return False

        if self.visible:
            if self.closerectangle and self.closerectangle.collidepoint(mouseposition):
                self.visible = False
            return True

        return False


    def handlekeydown(
        self,
        keyboardevent,
        provincemap,
        playercountry,
        countrytocolor,
        fallbackcolor,
        troopbadgelist,
        eventbus=None,
        currentturnnumber=0,
        commandcontext=None,
    ):
        if not self.enabled:
            return False

        if keyboardevent.key == pygame.K_BACKQUOTE or getattr(keyboardevent, "unicode", "") == "`":
            self.visible = not self.visible
            return True

        if not self.visible:
            return False

        eventmodifiers = getattr(keyboardevent, "mod", None)
        if eventmodifiers is None:
            try:
                eventmodifiers = pygame.key.get_mods()
            except pygame.error:
                eventmodifiers = 0

        if keyboardevent.key == pygame.K_ESCAPE:
            self.visible = False
        elif keyboardevent.key == pygame.K_RETURN:
            commandline = self.inputtext.strip()
            if commandline:
                if commandline.lower().startswith("aikey "):
                    self.loglines.append("> aikey [hidden]")
                else:
                    self.loglines.append("> " + commandline)
                outputline = rundevcommand(
                    commandline,
                    provincemap,
                    playercountry,
                    countrytocolor,
                    fallbackcolor,
                    troopbadgelist,
                    eventbus=eventbus,
                    currentturnnumber=currentturnnumber,
                    commandcontext=commandcontext,
                    aimanager=self.aimanager,
                    aipendingrequests=self.aipendingrequests,
                )
                self.loglines.append(outputline)
            self.inputtext = ""
        elif keyboardevent.key == pygame.K_BACKSPACE:
            self.inputtext = self.inputtext[:-1]
        elif keyboardevent.key == pygame.K_v and (eventmodifiers & (pygame.KMOD_CTRL | pygame.KMOD_META)):
            pastedtext = _cleanconsoleinputtext(_readclipboardtext())
            if pastedtext:
                self.inputtext += pastedtext
        elif keyboardevent.key == pygame.K_INSERT and (eventmodifiers & pygame.KMOD_SHIFT):
            pastedtext = _cleanconsoleinputtext(_readclipboardtext())
            if pastedtext:
                self.inputtext += pastedtext
        else:


            # TODO: filter some characters that could mess up the font rendering
            if keyboardevent.unicode and keyboardevent.unicode.isprintable():
                self.inputtext += keyboardevent.unicode

        return True


