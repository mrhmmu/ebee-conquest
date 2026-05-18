import heapq
import math
from collections import deque

from .core import getparentstateidfromprovinceid, getshapecenter, rectanglesclose
from .events import EngineEventType


terrainmovecostlookup = {
    "plains": 1.0,
    "forest": 1.25,
    "hills": 1.35,
    "mountains": 1.8,
    "desert": 1.2,
    "swamp": 1.5,
    "urban": 1.1,
}


entrenchmentturnrequired = 3
entrenchmentdefensemultiplier = 2.0
capitalcutoffsupplymultiplier = 0.70


# Keep border rendering/selection aligned with adjacency builder tolerances.
sharedLineTolerance = 0.9
sharedAlignmentTolerance = 0.16
sharedMinLength = 0.48 * 0.4


def getprovincecontroller(province):
    # get the current controller
    return province.get("controllercountry", province.get("country"))


def getprovinceowner(province):
    # get the original owner
    return province.get("ownercountry", province.get("country"))


def setprovincecontroller(province, countryname, countrycolor=None):
    #set the controller of the provincewhen occupied or annexed
    province["controllercountry"] = countryname
    province["country"] = countryname
    if countrycolor is not None:
        province["countrycolor"] = countrycolor


def markprovincetroopactivity(province, currentturnnumber):
    if currentturnnumber is None or province is None:
        return
    province["lasttroopactivityturn"] = int(currentturnnumber)


def getprovinceentrenchmentturns(province, currentturnnumber):
    if province is None or currentturnnumber is None:
        return 0

    troopcount = int(province.get("troops", 0))
    if troopcount <= 0:
        return 0

    lastactivityturn = int(province.get("lasttroopactivityturn", 0))
    return max(0, int(currentturnnumber) - lastactivityturn)


def isprovinceentrenched(province, currentturnnumber):
    return getprovinceentrenchmentturns(province, currentturnnumber) >= entrenchmentturnrequired


def allocatesurvivors(totalremainingtroops, contributionlist):
    if totalremainingtroops <= 0 or not contributionlist:
        return [0 for _ in contributionlist]

    totalcontribution = sum(max(0, int(contribution)) for contribution in contributionlist)
    if totalcontribution <= 0:
        return [0 for _ in contributionlist]

    baselist = []
    remainderlist = []
    assignedtotal = 0
    for index, contribution in enumerate(contributionlist):
        safecontribution = max(0, int(contribution))
        scaledvalue = safecontribution * int(totalremainingtroops)
        basevalue = scaledvalue // totalcontribution
        baselist.append(basevalue)
        assignedtotal += basevalue
        remainderlist.append((scaledvalue % totalcontribution, safecontribution, -index))

    remainingtroops = int(totalremainingtroops) - assignedtotal
    if remainingtroops > 0:
        remainderlist.sort(reverse=True)
        for _, _, negativeindex in remainderlist[:remainingtroops]:
            baselist[-negativeindex] += 1

    return baselist


def ensureprovincefrontlineassignments(province):
    frontlineassignments = province.get("frontlineassignments")
    if isinstance(frontlineassignments, dict):
        return frontlineassignments

    frontlineassignments = {}
    province["frontlineassignments"] = frontlineassignments
    return frontlineassignments


def getprovincefrontlinetroops(province, frontlineid=None):
    if province is None:
        return 0

    frontlineassignments = province.get("frontlineassignments")
    if not isinstance(frontlineassignments, dict):
        return 0

    if frontlineid is None:
        return sum(max(0, int(amount)) for amount in frontlineassignments.values())

    return max(0, int(frontlineassignments.get(frontlineid, 0)))


def setprovincefrontlinetroops(province, frontlineid, troopcount):
    if province is None or not frontlineid:
        return 0

    frontlineassignments = ensureprovincefrontlineassignments(province)
    safeamount = max(0, int(troopcount))
    if safeamount <= 0:
        frontlineassignments.pop(frontlineid, None)
    else:
        frontlineassignments[frontlineid] = safeamount
    return safeamount


def addprovincefrontlinetroops(province, frontlineid, troopdelta):
    currentamount = getprovincefrontlinetroops(province, frontlineid)
    return setprovincefrontlinetroops(province, frontlineid, currentamount + int(troopdelta))


def getprovinceunassignedtroops(province):
    if province is None:
        return 0
    totaltroops = max(0, int(province.get("troops", 0)))
    return max(0, totaltroops - getprovincefrontlinetroops(province))


def normalizefrontlineassignments(provincemap, activefrontlineidset=None):
    for province in provincemap.values():
        frontlineassignments = province.get("frontlineassignments")
        if not isinstance(frontlineassignments, dict):
            continue

        cleanedassignments = {}
        assignedtroops = 0
        for frontlineid, rawamount in frontlineassignments.items():
            if activefrontlineidset is not None and frontlineid not in activefrontlineidset:
                continue

            safeamount = max(0, int(rawamount))
            if safeamount <= 0:
                continue

            cleanedassignments[frontlineid] = safeamount
            assignedtroops += safeamount

        totaltroops = max(0, int(province.get("troops", 0)))
        if assignedtroops > totaltroops and cleanedassignments:
            frontlineidlist = sorted(cleanedassignments.keys())
            normalizedamounts = allocatesurvivors(
                totaltroops,
                [cleanedassignments[frontlineid] for frontlineid in frontlineidlist],
            )
            cleanedassignments = {
                frontlineid: amount
                for frontlineid, amount in zip(frontlineidlist, normalizedamounts)
                if amount > 0
            }

        province["frontlineassignments"] = cleanedassignments


# Movement starts
def prepareprovincemetadata(provincelist):
    enrichedlist = []
    for province in provincelist:
        enrichedprovince = dict(province)
        enrichedprovince["parentstateid"] = getparentstateidfromprovinceid(enrichedprovince["id"])
        enrichedprovince["terrain"] = "plains"
        enrichedprovince["troops"] = 0
        enrichedprovince["center"] = getshapecenter(enrichedprovince)
        enrichedprovince["ownercountry"] = None
        enrichedprovince["controllercountry"] = None
        enrichedprovince["country"] = None
        enrichedprovince["lasttroopactivityturn"] = 0
        enrichedprovince["frontlineassignments"] = {}
        enrichedlist.append(enrichedprovince)
    return enrichedlist


def buildprovinceadjacencygraph(provincemap, onprogress=None):
    provinceidlist = list(provincemap.keys())
    totalprovincecount = len(provinceidlist)

    # TEST OPTIMIZATION 3 APRIL
    totalprogresssteps = max(1, totalprovincecount * 2)
    if onprogress and not onprogress(0, totalprogresssteps):
        return None
    # larger cells will = faster but not as accurate
    gridcellsize = 32.0
    adjacencytestpadding = 1
    gridlookup = {}
    provinceentrylist = []


    for provinceindex, provinceid in enumerate(provinceidlist):
        provincerectangle = provincemap[provinceid]["rectangle"]
        minimumgridx = int(math.floor((provincerectangle.left - adjacencytestpadding) / gridcellsize))
        maximumgridx = int(math.floor((provincerectangle.right + adjacencytestpadding) / gridcellsize))
        minimumgridy = int(math.floor((provincerectangle.top - adjacencytestpadding) / gridcellsize))
        maximumgridy = int(math.floor((provincerectangle.bottom + adjacencytestpadding) / gridcellsize))
        provinceentrylist.append((provinceid, provincerectangle, minimumgridx, maximumgridx, minimumgridy, maximumgridy))
        for gridx in range(minimumgridx, maximumgridx + 1):
            for gridy in range(minimumgridy, maximumgridy + 1):
                gridlookup.setdefault((gridx, gridy), []).append(provinceindex)

        if onprogress and (provinceindex == 0 or (provinceindex + 1) % 200 == 0 or (provinceindex + 1) == totalprovincecount):
            if not onprogress(provinceindex + 1, totalprogresssteps):
                return None
    adjacencygraph = {provinceid: set() for provinceid in provinceidlist}
    for provinceindex, provinceentry in enumerate(provinceentrylist):
        provinceid, firstrectangle, minimumgridx, maximumgridx, minimumgridy, maximumgridy = provinceentry
        candidateindexset = set()



        for gridx in range(minimumgridx, maximumgridx + 1):
            for gridy in range(minimumgridy, maximumgridy + 1):
                for candidateindex in gridlookup.get((gridx, gridy), ()): 
                    #compare each pair once only, but avoid storing a global pair set
                    if candidateindex > provinceindex:
                        candidateindexset.add(candidateindex)




        for candidateindex in candidateindexset:
            candidateprovinceid, secondrectangle, dontneed, dontneed, dontneed, dontneed = provinceentrylist[candidateindex]
            if rectanglesclose(firstrectangle, secondrectangle, padding=adjacencytestpadding):
                firstprovince = provincemap.get(provinceid)
                secondprovince = provincemap.get(candidateprovinceid)
                if not firstprovince or not secondprovince:
                    continue

                # require a real shared border to avoid false positives from bounding-box proximity.
                sharedsegments = getsharedbordersegments(
                    firstprovince,
                    secondprovince,
                    linetolerancee=0.9,
                    alignmenttolerance=0.16,
                    minlength=0.48 * 0.4, # HIGHER WILL CAUSE BORDER ISSUES, LOWER WILL CAUSE PERFORMANCE ISSUES, 0.48 is the length of a diagonal of a grid cell, so this means the shared border must be at least 40% of that diagonal to count as adjacent
                )
                if not sharedsegments:
                    continue

                adjacencygraph[provinceid].add(candidateprovinceid)
                adjacencygraph[candidateprovinceid].add(provinceid)

        if onprogress and (provinceindex == 0 or (provinceindex + 1) % 100 == 0 or (provinceindex + 1) == totalprovincecount):
            if not onprogress(totalprovincecount + provinceindex + 1, totalprogresssteps):
                return None


    return adjacencygraph
    # optimization issue, cannot run on Benedict's AMD computer, might need to optimize the adjacency graph building


def getterrainmovecost(province):
    cachedmovecost = province.get("_terrainmovecost")
    if cachedmovecost is not None:
        return cachedmovecost

    movecost = terrainmovecostlookup.get(province.get("terrain", "plains"), 1.0)
    province["_terrainmovecost"] = movecost
    return movecost



# A* PATHFINDING ADAPTED FROM https://medium.com/@nicholas.w.swift/easy-a-star-pathfinding-7e6689c7f7b2
def findprovincepath(startprovinceid, goalprovinceid, provincemap, provincegraph, allowedprovinceidset=None):
    if startprovinceid not in provincemap or goalprovinceid not in provincemap:
        return []
    if allowedprovinceidset is not None:
        if startprovinceid not in allowedprovinceidset or goalprovinceid not in allowedprovinceidset:
            return []
    if startprovinceid == goalprovinceid:
        return [startprovinceid]

    goalcenter = provincemap[goalprovinceid]["center"]
    openheap = [(0.0, startprovinceid)]
    parentlookup = {}
    costlookup = {startprovinceid: 0.0}
    visitedset = set()
    infinityvalue = float("inf")

    #  A*
    while openheap:
        # total province with lowest cost
        _, currentprovinceid = heapq.heappop(openheap)
        if currentprovinceid in visitedset:
            continue

        if currentprovinceid == goalprovinceid:
            pathlist = [goalprovinceid]
            while pathlist[-1] in parentlookup:
                pathlist.append(parentlookup[pathlist[-1]])
            pathlist.reverse()
            return pathlist

        visitedset.add(currentprovinceid)
        # Ebee Super Optimization (ESO) 27/4
        # O(path*edges*geometry) -> O(path*edges)
        # cache per-edge move costs on province nodes
        currentprovince = provincemap[currentprovinceid]
        currentcenter = currentprovince["center"]
        currentcost = costlookup[currentprovinceid]
        stepcostcache = currentprovince.get("_neighborstepcostcache")
        if stepcostcache is None:
            stepcostcache = {}
            currentprovince["_neighborstepcostcache"] = stepcostcache

        for nextprovinceid in provincegraph.get(currentprovinceid, ()):
            if allowedprovinceidset is not None and nextprovinceid not in allowedprovinceidset:
                continue
            if nextprovinceid in visitedset:
                continue

            nextprovince = provincemap[nextprovinceid]
            nextcenter = nextprovince["center"]
            moveenergy = stepcostcache.get(nextprovinceid)
            if moveenergy is None:
                stepdistance = math.hypot(nextcenter[0] - currentcenter[0], nextcenter[1] - currentcenter[1])
                moveenergy = stepdistance * getterrainmovecost(nextprovince)
                stepcostcache[nextprovinceid] = moveenergy
            newcost = currentcost + moveenergy

            if newcost >= costlookup.get(nextprovinceid, infinityvalue):
                continue

            parentlookup[nextprovinceid] = currentprovinceid
            costlookup[nextprovinceid] = newcost
            estimateddistance = math.hypot(goalcenter[0] - nextcenter[0], goalcenter[1] - nextcenter[1])

            heapq.heappush(openheap, (newcost + estimateddistance, nextprovinceid))

    return []


def buildmovementordercurrentindex(movementorderlist, currentturnnumber=None):
    movementorderindex = {}
    for movementorder in movementorderlist:
        if int(movementorder.get("amount", 0)) <= 0:
            continue

        resumeturn = movementorder.get("_resumeonturn")
        if resumeturn is not None and currentturnnumber is not None:
            if int(currentturnnumber) < int(resumeturn):
                continue

        currentprovinceid = movementorder.get("current")
        if currentprovinceid is None:
            continue

        currentcountry = movementorder.get("controllercountry", movementorder.get("country"))
        if currentcountry is None:
            continue

        movementorderindex.setdefault((currentprovinceid, currentcountry), []).append(movementorder)

    return movementorderindex


def isprovinceconnectedtocapital(
    provinceid,
    countryname,
    provincemap,
    provincegraph,
    countrycapitalprovinceidlookup=None,
    connectioncache=None,
):
    if not countryname or not provinceid or not provincegraph or not countrycapitalprovinceidlookup:
        return True

    cachekey = (provinceid, countryname)
    if connectioncache is not None and cachekey in connectioncache:
        return connectioncache[cachekey]

    capitalprovinceid = countrycapitalprovinceidlookup.get(countryname)
    if not capitalprovinceid:
        return True

    startprovince = provincemap.get(provinceid)
    capitalprovince = provincemap.get(capitalprovinceid)
    if not startprovince or not capitalprovince:
        return True

    if getprovincecontroller(startprovince) != countryname:
        connected = False
    elif getprovincecontroller(capitalprovince) != countryname:
        connected = False
    elif provinceid == capitalprovinceid:
        connected = True
    else:
        connected = False
        visited = {provinceid}
        searchqueue = deque([provinceid])
        while searchqueue:
            currentprovinceid = searchqueue.popleft()
            for neighborid in provincegraph.get(currentprovinceid, ()):
                if neighborid in visited:
                    continue
                neighborprovince = provincemap.get(neighborid)
                if not neighborprovince or getprovincecontroller(neighborprovince) != countryname:
                    continue
                if neighborid == capitalprovinceid:
                    connected = True
                    searchqueue.clear()
                    break
                visited.add(neighborid)
                searchqueue.append(neighborid)

    if connectioncache is not None:
        connectioncache[cachekey] = connected
    return connected


def getcapitalsupplymultiplier(
    provinceid,
    countryname,
    provincemap,
    provincegraph,
    countrycapitalprovinceidlookup=None,
    connectioncache=None,
):
    if isprovinceconnectedtocapital(
        provinceid,
        countryname,
        provincemap,
        provincegraph,
        countrycapitalprovinceidlookup=countrycapitalprovinceidlookup,
        connectioncache=connectioncache,
    ):
        return 1.0
    return capitalcutoffsupplymultiplier


def processmovementorders(
    movementorderlist,
    provincemap,
    emit,
    currentturnnumber=None,
    provincegraph=None,
    countrycapitalprovinceidlookup=None,
):
    # MOVEMENT processing
    finishedorderlist = []
    supplyconnectioncache = {}
    # Ebee Super Optimization (ESO) 27/4
    # O(m*m) -> O(m)
    # index active orders by current province and country for defender lookups
    currentorderindex = buildmovementordercurrentindex(movementorderlist, currentturnnumber=currentturnnumber)

    def markorderfinished(movementorder, reasontext):
        if movementorder not in finishedorderlist:
            finishedorderlist.append(movementorder)
        movementorder["_finishreason"] = reasontext

    def getorderindexkey(movementorder):
        if int(movementorder.get("amount", 0)) <= 0:
            return None

        resumeturn = movementorder.get("_resumeonturn")
        if resumeturn is not None and currentturnnumber is not None:
            if int(currentturnnumber) < int(resumeturn):
                return None

        currentprovinceid = movementorder.get("current")
        if currentprovinceid is None:
            return None

        currentcountry = movementorder.get("controllercountry", movementorder.get("country"))
        if currentcountry is None:
            return None

        return (currentprovinceid, currentcountry)

    def reindexorder(movementorder, previouskey):
        if previouskey is not None:
            bucket = currentorderindex.get(previouskey)
            if bucket:
                try:
                    bucket.remove(movementorder)
                except ValueError:
                    pass
                if not bucket:
                    currentorderindex.pop(previouskey, None)

        newkey = getorderindexkey(movementorder)
        if newkey is not None:
            currentorderindex.setdefault(newkey, []).append(movementorder)
        return newkey

    def interruptdefendingorders(targetprovinceid, defendingcountry, excludedorder):
        interruptedorderlist = []
        totalmovingdefenders = 0
        for candidateorder in list(currentorderindex.get((targetprovinceid, defendingcountry), ())):
            if candidateorder is excludedorder:
                continue

            totalmovingdefenders += int(candidateorder.get("amount", 0))
            interruptedorderlist.append(candidateorder)

        return interruptedorderlist, totalmovingdefenders

    for movementorder in movementorderlist:
        orderindexkey = getorderindexkey(movementorder)
        resumeturn = movementorder.get("_resumeonturn")
        if resumeturn is not None and currentturnnumber is not None:
            if int(currentturnnumber) < int(resumeturn):
                continue
            movementorder.pop("_resumeonturn", None)

        if movementorder.pop("_skipnextprocessing", False):
            continue

        if int(movementorder.get("amount", 0)) <= 0:
            markorderfinished(movementorder, movementorder.get("_finishreason", "depleted"))
            continue

        movementpoints = 1.0 * float(movementorder.get("speedmodifier", 1.0))
        pathlist = movementorder["path"]
        currentpathindex = movementorder["index"]
        movingcountry = movementorder.get("controllercountry", movementorder.get("country"))
        movingcountrycolor = movementorder.get("countrycolor")

        while currentpathindex < len(pathlist) - 1:
            nextprovinceid = pathlist[currentpathindex + 1]
            nextprovince = provincemap[nextprovinceid]
            movecost = getterrainmovecost(nextprovince)
            # move next turn if not enough
            if movementpoints < movecost:
                break

            if movingcountry is None:
                movingcountry = getprovincecontroller(provincemap[pathlist[currentpathindex]])
                movementorder["controllercountry"] = movingcountry
                movementorder["country"] = movingcountry
                orderindexkey = reindexorder(movementorder, orderindexkey)

            nextcountry = getprovincecontroller(nextprovince)
            if (
                movingcountry is not None
                and nextcountry is not None
                and nextcountry != movingcountry
                and nextprovince["troops"] >= 0
            ):
                attackers = movementorder["amount"]
                interruptedorderlist, movingdefenders = interruptdefendingorders(
                    nextprovinceid,
                    nextcountry,
                    movementorder,
                )

                basedefenders = int(nextprovince.get("troops", 0))
                defenders = basedefenders + movingdefenders

                attackerprovinceid = pathlist[currentpathindex]
                attackermultiplier = getcapitalsupplymultiplier(
                    attackerprovinceid,
                    movingcountry,
                    provincemap,
                    provincegraph,
                    countrycapitalprovinceidlookup=countrycapitalprovinceidlookup,
                    connectioncache=supplyconnectioncache,
                )
                defendermultiplier = getcapitalsupplymultiplier(
                    nextprovinceid,
                    nextcountry,
                    provincemap,
                    provincegraph,
                    countrycapitalprovinceidlookup=countrycapitalprovinceidlookup,
                    connectioncache=supplyconnectioncache,
                )
                entrenched = isprovinceentrenched(nextprovince, currentturnnumber)
                defensemultiplier = entrenchmentdefensemultiplier if entrenched else 1.0
                totaldefensemultiplier = defensemultiplier * defendermultiplier
                effectiveattackers = int(math.ceil(attackers * attackermultiplier))
                effectivedefenders = int(math.ceil(defenders * totaldefensemultiplier))

                if defenders > 0 and effectiveattackers <= effectivedefenders:
                    remainingeffective = effectivedefenders - effectiveattackers
                    remainingdefenders = int(math.ceil(remainingeffective / totaldefensemultiplier)) if remainingeffective > 0 else 0
                    remainingsurvivors = max(0, min(defenders, remainingdefenders))

                    interruptedamountlist = [int(order.get("amount", 0)) for order in interruptedorderlist]
                    survivorallocation = allocatesurvivors(
                        remainingsurvivors,
                        [basedefenders] + interruptedamountlist,
                    )
                    nextprovince["troops"] = survivorallocation[0] if survivorallocation else remainingsurvivors

                    for interruptedorder, survivingtroops in zip(interruptedorderlist, survivorallocation[1:]):
                        interruptedorderindexkey = getorderindexkey(interruptedorder)
                        if survivingtroops <= 0:
                            interruptedorder["amount"] = 0
                            markorderfinished(interruptedorder, "interrupted_defense")
                            reindexorder(interruptedorder, interruptedorderindexkey)
                            continue

                        interruptedorder["amount"] = survivingtroops
                        if currentturnnumber is None:
                            interruptedorder["_skipnextprocessing"] = True
                        else:
                            interruptedorder["_resumeonturn"] = int(currentturnnumber) + 1
                        reindexorder(interruptedorder, interruptedorderindexkey)

                    markprovincetroopactivity(nextprovince, currentturnnumber)

                    # combat resolved
                    if emit is not None:
                        emit(
                            EngineEventType.COMBATRESOLVED,
                            {
                                "provinceId": nextprovinceid,
                                "attackerCountry": movingcountry,
                                "defenderCountry": nextcountry,
                                "attackersBefore": attackers,
                                "defendersBefore": defenders,
                                "attackersAfter": 0,
                                "defendersAfter": nextprovince["troops"],
                                "defenseMultiplier": defensemultiplier,
                                "defendersEntrenched": entrenched,
                                "attackerSupplyMultiplier": attackermultiplier,
                                "defenderSupplyMultiplier": defendermultiplier,
                                "attackerCutOffFromCapital": attackermultiplier < 1.0,
                                "defenderCutOffFromCapital": defendermultiplier < 1.0,
                            },
                        )

                    movementorder["amount"] = 0
                    markorderfinished(movementorder, "defeated")
                    orderindexkey = reindexorder(movementorder, orderindexkey)
                    break

                if defenders > 0:
                    remainingeffectiveattackers = max(0, effectiveattackers - effectivedefenders)
                    remainingattackers = (
                        int(math.ceil(remainingeffectiveattackers / attackermultiplier))
                        if remainingeffectiveattackers > 0
                        else 0
                    )
                    movementorder["amount"] = max(0, min(attackers, remainingattackers))
                    nextprovince["troops"] = 0

                    for interruptedorder in interruptedorderlist:
                        interruptedorderindexkey = getorderindexkey(interruptedorder)
                        interruptedorder["amount"] = 0
                        markorderfinished(interruptedorder, "interrupted_defense")
                        reindexorder(interruptedorder, interruptedorderindexkey)

                    markprovincetroopactivity(nextprovince, currentturnnumber)

                    #comabt resolved
                    if emit is not None:
                        emit(
                            EngineEventType.COMBATRESOLVED,
                            {
                                "provinceId": nextprovinceid,
                                "attackerCountry": movingcountry,
                                "defenderCountry": nextcountry,
                                "attackersBefore": attackers,
                                "defendersBefore": defenders,
                                "attackersAfter": movementorder["amount"],
                                "defendersAfter": 0,
                                "defenseMultiplier": defensemultiplier,
                                "defendersEntrenched": entrenched,
                                "attackerSupplyMultiplier": attackermultiplier,
                                "defenderSupplyMultiplier": defendermultiplier,
                                "attackerCutOffFromCapital": attackermultiplier < 1.0,
                                "defenderCutOffFromCapital": defendermultiplier < 1.0,
                            },
                        )

            movementpoints -= movecost
            currentpathindex += 1

            if (
                movingcountry is not None
                and nextcountry is not None
                and nextcountry != movingcountry
                and nextprovince["troops"] <= 0
            ):
                previouscontroller = nextcountry
                setprovincecontroller(nextprovince, movingcountry, movingcountrycolor)
                markprovincetroopactivity(nextprovince, currentturnnumber)
                if emit is not None:
                    emit(
                        EngineEventType.PROVINCECONTROLCHANGED,
                        {
                            "provinceId": nextprovinceid,
                            "previousController": previouscontroller,
                            "newController": movingcountry,
                        },
                    )  #link to event

            # Move at most one hop per turn so units cannot skip provinces.
            break

        movementorder["index"] = currentpathindex
        movementorder["current"] = pathlist[currentpathindex]
        orderindexkey = reindexorder(movementorder, orderindexkey)

        if movementorder["amount"] <= 0:
            markorderfinished(movementorder, movementorder.get("_finishreason", "depleted"))


            if emit is not None:
                emit(
                    EngineEventType.MOVEORDERFINISHED,
                    {
                        "path": list(pathlist),
                        "finalProvinceId": pathlist[currentpathindex],
                        "remainingTroops": 0,
                        "reason": movementorder.get("_finishreason", "depleted"),
                    },
                )

        elif currentpathindex >= len(pathlist) - 1:
            destinationprovinceid = pathlist[-1]
            provincemap[destinationprovinceid]["troops"] += movementorder["amount"]
            frontlineid = movementorder.get("frontlineid")
            if frontlineid:
                addprovincefrontlinetroops(
                    provincemap[destinationprovinceid],
                    frontlineid,
                    movementorder["amount"],
                )
            markprovincetroopactivity(provincemap[destinationprovinceid], currentturnnumber)
            markorderfinished(movementorder, "arrived")


            if emit is not None:
                emit(
                    EngineEventType.MOVEORDERFINISHED,
                    {
                        "path": list(pathlist),
                        "finalProvinceId": destinationprovinceid,
                        "remainingTroops": movementorder["amount"],
                        "reason": "arrived",
                    },
                )

    for finishedorder in finishedorderlist:
        finishedorder.pop("_finishreason", None)
        movementorderlist.remove(finishedorder)


def splitselectedtroops(provincemap, provincegraph, selectedprovinceids, playercountry):

    validselectedprovinceids = []
    for provinceid in sorted(set(selectedprovinceids or ())):
        province = provincemap.get(provinceid)
        if not province:
            continue
        if getprovincecontroller(province) != playercountry:
            continue
        validselectedprovinceids.append(provinceid)


    if not validselectedprovinceids:

        return {
            "success": False,
            "selectedprovinceids": [],
            "primaryprovinceid": None,
            "movedtroops": 0,
        }



    if len(validselectedprovinceids) == 1:
        sourceprovinceid = validselectedprovinceids[0]
        sourceprovince = provincemap[sourceprovinceid]
        sourcetroops = int(sourceprovince.get("troops", 0))


        if sourcetroops < 2:
            return {
                "success": False,
                "selectedprovinceids": validselectedprovinceids,
                "primaryprovinceid": sourceprovinceid,
                "movedtroops": 0,
            }

        friendlyneighborids = []


        for neighborprovinceid in provincegraph.get(sourceprovinceid, ()):
            neighborprovince = provincemap.get(neighborprovinceid)
            if not neighborprovince:
                continue
            if getprovincecontroller(neighborprovince) != playercountry:
                continue
            friendlyneighborids.append(neighborprovinceid)



        if not friendlyneighborids:
            return {
                "success": False,
                "selectedprovinceids": validselectedprovinceids,
                "primaryprovinceid": sourceprovinceid,
                "movedtroops": 0,
            }

        targetprovinceid = min(
            friendlyneighborids,
            key=lambda provinceid: int(provincemap[provinceid].get("troops", 0)),
        )
        movedtroops = sourcetroops // 2


        if movedtroops <= 0:
            return {
                "success": False,
                "selectedprovinceids": validselectedprovinceids,
                "primaryprovinceid": sourceprovinceid,
                "movedtroops": 0,
            }

        sourceprovince["troops"] = sourcetroops - movedtroops
        provincemap[targetprovinceid]["troops"] += movedtroops

        return {
            "success": True,
            "selectedprovinceids": [sourceprovinceid, targetprovinceid],
            "primaryprovinceid": sourceprovinceid,
            "movedtroops": movedtroops,
        }


    totaltroops = sum(int(provincemap[provinceid].get("troops", 0)) for provinceid in validselectedprovinceids)
    if totaltroops <= 0:
        return {
            "success": False,
            "selectedprovinceids": validselectedprovinceids,
            "primaryprovinceid": validselectedprovinceids[0],
            "movedtroops": 0,
        }
    

    provincecount = len(validselectedprovinceids)
    baseallocation = totaltroops // provincecount
    remainder = totaltroops % provincecount


    for provinceindex, provinceid in enumerate(validselectedprovinceids):
        provincemap[provinceid]["troops"] = baseallocation + (1 if provinceindex < remainder else 0)

    return {
        "success": True,
        "selectedprovinceids": validselectedprovinceids,
        "primaryprovinceid": validselectedprovinceids[0],
        "movedtroops": totaltroops,
    }




def mergeselectedtroops(provincemap, selectedprovinceids, playercountry, targetprovinceid=None):

    validselectedprovinceids = []
    for provinceid in sorted(set(selectedprovinceids or ())):
        province = provincemap.get(provinceid)
        if not province:
            continue
        if getprovincecontroller(province) != playercountry:
            continue
        validselectedprovinceids.append(provinceid)


    if not validselectedprovinceids:
        return {
            "success": False,
            "selectedprovinceids": [],
            "primaryprovinceid": None,
            "mergedtroops": 0,
        }


    if targetprovinceid not in validselectedprovinceids:
        targetprovinceid = validselectedprovinceids[0]

    totaltroops = sum(int(provincemap[provinceid].get("troops", 0)) for provinceid in validselectedprovinceids)

    for provinceid in validselectedprovinceids:

        provincemap[provinceid]["troops"] = 0
    provincemap[targetprovinceid]["troops"] = totaltroops



    return {
        "success": True,
        "selectedprovinceids": [targetprovinceid],
        "primaryprovinceid": targetprovinceid,
        "mergedtroops": totaltroops,
    }






def getborderedgekey(firstprovinceid, secondprovinceid):
    if firstprovinceid <= secondprovinceid:
        return (firstprovinceid, secondprovinceid)
    return (secondprovinceid, firstprovinceid)


bordersegmentcache = {}
edgegridcellsize = 24.0




def snappoint(point, precision=2):
    return (round(float(point[0]), precision), round(float(point[1]), precision))




def getedgekey(pointa, pointb, precision=2):
    snappeda = snappoint(pointa, precision=precision)
    snappedb = snappoint(pointb, precision=precision)
    if snappeda <= snappedb:
        return (snappeda, snappedb)
    return (snappedb, snappeda)


def iterateprovinceedge(province):
    for polygon in province.get("polygons", ()):
        polygonpoints = polygon.get("points", ())
        pointcount = len(polygonpoints)
        if pointcount < 2:
            continue
        for pointindex in range(pointcount):
            startpoint = polygonpoints[pointindex]
            endpoint = polygonpoints[(pointindex + 1) % pointcount]
            if abs(startpoint[0] - endpoint[0]) <= 1e-9 and abs(startpoint[1] - endpoint[1]) <= 1e-9:
                continue
            yield startpoint, endpoint


def getprovinceedgedata(province):
    cachedentries = province.get("_edgeentriescache")
    if cachedentries is not None:
        return cachedentries

    edgeentries = []
    for startpoint, endpoint in iterateprovinceedge(province):
        startx, starty = startpoint
        endx, endy = endpoint
        dx = endx - startx
        dy = endy - starty
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            continue
        edgeentries.append(
            {
                "start": (float(startx), float(starty)),
                "end": (float(endx), float(endy)),
                "length": length,
                "ux": dx / length,
                "uy": dy / length,
                "minx": min(startx, endx),
                "maxx": max(startx, endx),
                "miny": min(starty, endy),
                "maxy": max(starty, endy),
            }
        )

    province["_edgeentriescache"] = edgeentries
    return edgeentries


def getprovinceedgegrid(province, cellsize=edgegridcellsize):
    edgeentries = getprovinceedgedata(province)
    cachedgrid = province.get("_edgegridcache")
    if cachedgrid is not None:
        if cachedgrid.get("cellsize") == cellsize and cachedgrid.get("edgeentries") is edgeentries:
            return cachedgrid

    gridlookup = {}
    for edgeindex, edgeentry in enumerate(edgeentries):
        minimumgridx = int(math.floor(edgeentry["minx"] / cellsize))
        maximumgridx = int(math.floor(edgeentry["maxx"] / cellsize))
        minimumgridy = int(math.floor(edgeentry["miny"] / cellsize))
        maximumgridy = int(math.floor(edgeentry["maxy"] / cellsize))
        for gridx in range(minimumgridx, maximumgridx + 1):
            for gridy in range(minimumgridy, maximumgridy + 1):
                gridlookup.setdefault((gridx, gridy), []).append(edgeindex)

    cachedgrid = {
        "cellsize": cellsize,
        "edgeentries": edgeentries,
        "grid": gridlookup,
    }
    province["_edgegridcache"] = cachedgrid
    return cachedgrid


def iterprovinceedgecandidates(province, queryedgeentry, padding, cellsize=edgegridcellsize):
    cachedgrid = getprovinceedgegrid(province, cellsize=cellsize)
    edgeentries = cachedgrid["edgeentries"]
    gridlookup = cachedgrid["grid"]
    minimumgridx = int(math.floor((queryedgeentry["minx"] - padding) / cellsize))
    maximumgridx = int(math.floor((queryedgeentry["maxx"] + padding) / cellsize))
    minimumgridy = int(math.floor((queryedgeentry["miny"] - padding) / cellsize))
    maximumgridy = int(math.floor((queryedgeentry["maxy"] + padding) / cellsize))
    seenedgeindexes = set()

    for gridx in range(minimumgridx, maximumgridx + 1):
        for gridy in range(minimumgridy, maximumgridy + 1):
            for edgeindex in gridlookup.get((gridx, gridy), ()):
                if edgeindex in seenedgeindexes:
                    continue
                seenedgeindexes.add(edgeindex)
                yield edgeentries[edgeindex]


def pointvsline_distance(point, lineentry):
    px, py = point
    sx, sy = lineentry["start"]
    ux = lineentry["ux"]
    uy = lineentry["uy"]
    # perpendicular line


    return abs((px - sx) * (-uy) + (py - sy) * ux)


def lineuppointonline(point, lineentry):
    px, py = point
    sx, sy = lineentry["start"]
    ux = lineentry["ux"]
    uy = lineentry["uy"]

    return (px - sx) * ux + (py - sy) * uy


def getoverlapsegment(firstentry, secondentry, linetolerancee, alignmenttolerance, minlength):
    # Quick reject by expanded bounding boxes.
    if firstentry["maxx"] + linetolerancee < secondentry["minx"]:
        return None
    if secondentry["maxx"] + linetolerancee < firstentry["minx"]:
        return None
    if firstentry["maxy"] + linetolerancee < secondentry["miny"]:
        return None
    if secondentry["maxy"] + linetolerancee < firstentry["miny"]:
        return None

    crossvalue = abs(firstentry["ux"] * secondentry["uy"] - firstentry["uy"] * secondentry["ux"])
    if crossvalue > alignmenttolerance:
        return None

    # need alignment for both ways
    if (
        pointvsline_distance(secondentry["start"], firstentry) > linetolerancee
        and pointvsline_distance(secondentry["end"], firstentry) > linetolerancee
    ):
        return None
    if (
        pointvsline_distance(firstentry["start"], secondentry) > linetolerancee
        and pointvsline_distance(firstentry["end"], secondentry) > linetolerancee
    ):
        return None



    secondstartprojection = lineuppointonline(secondentry["start"], firstentry)
    secondendprojection = lineuppointonline(secondentry["end"], firstentry)

    overlapstart = max(0.0, min(secondstartprojection, secondendprojection))
    overlapend = min(firstentry["length"], max(secondstartprojection, secondendprojection))
    if overlapend - overlapstart < minlength:
        return None

    segmentstart = (
        firstentry["start"][0] + firstentry["ux"] * overlapstart,
        firstentry["start"][1] + firstentry["uy"] * overlapstart,
    )
    segmentend = (
        firstentry["start"][0] + firstentry["ux"] * overlapend,
        firstentry["start"][1] + firstentry["uy"] * overlapend,
    )
    return segmentstart, segmentend


def getsharedbordersegments(
    playerprovince,
    foreignprovince,
    linetolerancee=1.1,
    alignmenttolerance=0.16,
    minlength=0.55,
    keyprecision=2,
):
    

    playerprovinceid = playerprovince.get("id")
    foreignprovinceid = foreignprovince.get("id")
    if playerprovinceid and foreignprovinceid:
        cachekey = (
            playerprovinceid if playerprovinceid <= foreignprovinceid else foreignprovinceid,
            foreignprovinceid if playerprovinceid <= foreignprovinceid else playerprovinceid,
        )
        cachedsegments = bordersegmentcache.get(cachekey)
        if cachedsegments is not None:
            return list(cachedsegments)

    playeredgeentries = getprovinceedgedata(playerprovince)
    sharedsegmentlookup = {}

    for playeredgeentry in playeredgeentries:
        for foreignedgeentry in iterprovinceedgecandidates(
            foreignprovince,
            playeredgeentry,
            padding=linetolerancee,
        ):
            overlappedsegment = getoverlapsegment(
                playeredgeentry,
                foreignedgeentry,
                linetolerancee,
                alignmenttolerance,
                minlength,
            )
            if not overlappedsegment:
                continue

            segmentstart, segmentend = overlappedsegment
            segmentkey = getedgekey(segmentstart, segmentend, precision=keyprecision)
            existingsegment = sharedsegmentlookup.get(segmentkey)
            if existingsegment is None:
                sharedsegmentlookup[segmentkey] = overlappedsegment
                continue

            existinglength = math.hypot(
                existingsegment[1][0] - existingsegment[0][0],
                existingsegment[1][1] - existingsegment[0][1],
            )
            candidatelength = math.hypot(
                segmentend[0] - segmentstart[0],
                segmentend[1] - segmentstart[1],
            )
            if candidatelength > existinglength:
                sharedsegmentlookup[segmentkey] = overlappedsegment

    sharedsegmentlist = list(sharedsegmentlookup.values())
    if playerprovinceid and foreignprovinceid:
        bordersegmentcache[cachekey] = list(sharedsegmentlist)
    return sharedsegmentlist


def getcountryborderedges(provincemap, provincegraph, countryname):
    if not countryname:
        return []

    borderedgelist = []
    visitededgekeyset = set()


    for playerprovinceid, province in provincemap.items():

        if getprovincecontroller(province) != countryname:
            continue

        for foreignprovinceid in provincegraph.get(playerprovinceid, ()):
            foreignprovince = provincemap.get(foreignprovinceid)
            if not foreignprovince:
                continue

            foreigncountry = getprovincecontroller(foreignprovince)
            if foreigncountry == countryname:
                continue

            sharedsegments = getsharedbordersegments(
                province,
                foreignprovince,
                linetolerancee=sharedLineTolerance,
                alignmenttolerance=sharedAlignmentTolerance,
                minlength=sharedMinLength,
            )
            if not sharedsegments:
                continue

            edgekey = getborderedgekey(playerprovinceid, foreignprovinceid)
            if edgekey in visitededgekeyset:
                continue

            visitededgekeyset.add(edgekey)
            borderedgelist.append(
                {
                    "playerprovinceid": playerprovinceid,
                    "foreignprovinceid": foreignprovinceid,
                    "foreigncountry": foreigncountry,
                    "edgekey": edgekey,
                    "worldsegments": sharedsegments,
                }
            )

    borderedgelist.sort(key=lambda edge: edge["edgekey"]) #sort by edge key to ensure consistent order
    return borderedgelist




def getborderworldsegments(provincemap, borderedge):

    if not borderedge:
        return []

    cachedworldsegments = borderedge.get("worldsegments")
    if cachedworldsegments is not None:
        return list(cachedworldsegments)

    playerprovince = provincemap.get(borderedge.get("playerprovinceid"))
    foreignprovince = provincemap.get(borderedge.get("foreignprovinceid"))
    if not playerprovince or not foreignprovince:
        return []

    sharedsegments = getsharedbordersegments(
        playerprovince,
        foreignprovince,
        linetolerancee=sharedLineTolerance,
        alignmenttolerance=sharedAlignmentTolerance,
        minlength=sharedMinLength,
    )
    if sharedsegments:
        return sharedsegments

    return []


def getfrontlineprovinces(provincemap, provincegraph, playercountry, anchorprovinceid, targetcountry=None, nearbydepth=2):
    anchorprovince = provincemap.get(anchorprovinceid)
    if not anchorprovince or getprovincecontroller(anchorprovince) != playercountry:
        return set()

    frontierprovinceidset = set()
    for provinceid, province in provincemap.items():
        if getprovincecontroller(province) != playercountry:
            continue

        provincehasmatchingborder = False
        for neighborprovinceid in provincegraph.get(provinceid, ()):
            neighborprovince = provincemap.get(neighborprovinceid)
            if not neighborprovince:
                continue
            neighborcountry = getprovincecontroller(neighborprovince)
            if neighborcountry == playercountry:
                continue
            if targetcountry is not None and neighborcountry != targetcountry:
                continue
            if not getsharedbordersegments(province, neighborprovince):
                continue
            provincehasmatchingborder = True
            break

        if provincehasmatchingborder:
            frontierprovinceidset.add(provinceid)

    traversalprovinceidset = {anchorprovinceid}
    if frontierprovinceidset:
        traversalprovinceidset.update(frontierprovinceidset)
        depthlimit = max(0, int(nearbydepth))
        frontierdepthlookup = {provinceid: 0 for provinceid in frontierprovinceidset}
        # Ebee Super Optimization (ESO) 27/4
        # O(n*n) -> O(n)
        # use deque queues for frontier breadth-first searches
        openlist = deque(frontierprovinceidset)
        while openlist:
            currentprovinceid = openlist.popleft()
            currentdepth = frontierdepthlookup[currentprovinceid]
            if currentdepth >= depthlimit:
                continue

            for neighborprovinceid in provincegraph.get(currentprovinceid, ()):
                neighborprovince = provincemap.get(neighborprovinceid)
                if not neighborprovince:
                    continue
                if getprovincecontroller(neighborprovince) != playercountry:
                    continue

                nextdepth = currentdepth + 1
                existingdepth = frontierdepthlookup.get(neighborprovinceid)
                if existingdepth is not None and existingdepth <= nextdepth:
                    continue
                frontierdepthlookup[neighborprovinceid] = nextdepth
                traversalprovinceidset.add(neighborprovinceid)
                openlist.append(neighborprovinceid)

    frontlineprovinceidset = set()
    openlist = deque([anchorprovinceid])
    visitedprovinceidset = set()
    while openlist:
        currentprovinceid = openlist.popleft()
        if currentprovinceid in visitedprovinceidset:
            continue
        visitedprovinceidset.add(currentprovinceid)

        currentprovince = provincemap.get(currentprovinceid)
        if not currentprovince or getprovincecontroller(currentprovince) != playercountry:
            continue
        if currentprovinceid not in traversalprovinceidset:
            continue

        if currentprovinceid in frontierprovinceidset:
            frontlineprovinceidset.add(currentprovinceid)

        for neighborprovinceid in provincegraph.get(currentprovinceid, ()):
            neighborprovince = provincemap.get(neighborprovinceid)
            if not neighborprovince:
                continue
            if getprovincecontroller(neighborprovince) != playercountry:
                continue
            if neighborprovinceid in traversalprovinceidset:
                openlist.append(neighborprovinceid)

    if not frontlineprovinceidset and anchorprovinceid in provincemap:
        frontlineprovinceidset.add(anchorprovinceid)

    return frontlineprovinceidset


def buildbalancedtransferplan(sourceamountlookup, targetprovinceids):
    validsourceprovinceids = [
        provinceid
        for provinceid, amount in sorted(sourceamountlookup.items())
        if int(amount) > 0
    ]
    if not validsourceprovinceids or not targetprovinceids:
        return {
            "totalassignedtroops": 0,
            "transferplan": [],
            "targetprovinceids": [],
        }

    sourceremaininglookup = {
        provinceid: max(0, int(sourceamountlookup.get(provinceid, 0)))
        for provinceid in validsourceprovinceids
    }
    totalavailabletroops = sum(sourceremaininglookup.values())
    if totalavailabletroops <= 0:
        return {
            "totalassignedtroops": 0,
            "transferplan": [],
            "targetprovinceids": [],
        }

    targetcount = len(targetprovinceids)
    baseallocation = totalavailabletroops // targetcount
    remainder = totalavailabletroops % targetcount
    targetdesiredlookup = {}
    for targetindex, provinceid in enumerate(targetprovinceids):
        targetdesiredlookup[provinceid] = baseallocation + (1 if targetindex < remainder else 0)

    transferplan = []
    # Keep troops already sitting in a target province there before planning
    # any transfers. This avoids sideways shuffling on an unchanged frontline.
    targetremaininglookup = dict(targetdesiredlookup)
    for targetprovinceid in targetprovinceids:
        stationedtroops = sourceremaininglookup.get(targetprovinceid, 0)
        if stationedtroops <= 0:
            continue

        retainedtroops = min(targetremaininglookup.get(targetprovinceid, 0), stationedtroops)
        if retainedtroops <= 0:
            continue

        transferplan.append(
            {
                "sourceprovinceid": targetprovinceid,
                "targetprovinceid": targetprovinceid,
                "amount": retainedtroops,
            }
        )
        sourceremaininglookup[targetprovinceid] -= retainedtroops
        targetremaininglookup[targetprovinceid] -= retainedtroops

    surplussourceprovinceids = [
        provinceid for provinceid in validsourceprovinceids if sourceremaininglookup.get(provinceid, 0) > 0
    ]
    sourcecursor = 0
    for targetprovinceid in targetprovinceids:
        neededtroops = targetremaininglookup.get(targetprovinceid, 0)
        while neededtroops > 0 and sourcecursor < len(surplussourceprovinceids):
            sourceprovinceid = surplussourceprovinceids[sourcecursor]
            sourceavailable = sourceremaininglookup.get(sourceprovinceid, 0)
            if sourceavailable <= 0:
                sourcecursor += 1
                continue

            assignedtroops = min(neededtroops, sourceavailable)
            if assignedtroops <= 0:
                sourcecursor += 1
                continue

            transferplan.append(
                {
                    "sourceprovinceid": sourceprovinceid,
                    "targetprovinceid": targetprovinceid,
                    "amount": assignedtroops,
                }
            )
            sourceremaininglookup[sourceprovinceid] -= assignedtroops
            neededtroops -= assignedtroops
            if sourceremaininglookup[sourceprovinceid] <= 0:
                sourcecursor += 1

    totalassignedtroops = sum(entry["amount"] for entry in transferplan)
    effectivefrontlineprovinceids = []
    seenprovinceids = set()
    for transferentry in transferplan:
        targetprovinceid = transferentry["targetprovinceid"]
        if targetprovinceid in seenprovinceids:
            continue
        seenprovinceids.add(targetprovinceid)
        effectivefrontlineprovinceids.append(targetprovinceid)

    return {
        "totalassignedtroops": totalassignedtroops,
        "transferplan": transferplan,
        "targetprovinceids": effectivefrontlineprovinceids,
    }


def buildfrontlinetransferplan(provincemap, selectedprovinceids, frontlineprovinceids, playercountry):

    validsourceprovinceids = []
    sourceamountlookup = {}
    for provinceid in sorted(set(selectedprovinceids or ())):
        province = provincemap.get(provinceid)
        if not province:
            continue
        if getprovincecontroller(province) != playercountry:
            continue
        availabletroops = getprovinceunassignedtroops(province)
        if availabletroops <= 0:
            continue
        validsourceprovinceids.append(provinceid)
        sourceamountlookup[provinceid] = availabletroops

    if not validsourceprovinceids:
        return {
            "totalassignedtroops": 0,
            "transferplan": [],
            "targetprovinceids": [],
        }

    validtargetprovinceids = []
    for provinceid in frontlineprovinceids or ():
        province = provincemap.get(provinceid)
        if not province:
            continue
        if getprovincecontroller(province) != playercountry:
            continue
        if provinceid not in validtargetprovinceids:
            validtargetprovinceids.append(provinceid)

    if not validtargetprovinceids:
        return {
            "totalassignedtroops": 0,
            "transferplan": [],
            "targetprovinceids": [],
        }

    return buildbalancedtransferplan(sourceamountlookup, validtargetprovinceids)


def buildfrontlinedivisiontransferplan(
    provincemap,
    frontlineid,
    frontlineprovinceids,
    playercountry,
    currentturnnumber=None,
):
    validtargetprovinceids = []
    targetprovinceidset = set()
    for provinceid in frontlineprovinceids or ():
        province = provincemap.get(provinceid)
        if not province:
            continue
        if getprovincecontroller(province) != playercountry:
            continue
        if provinceid in targetprovinceidset:
            continue
        validtargetprovinceids.append(provinceid)
        targetprovinceidset.add(provinceid)

    if not validtargetprovinceids:
        return {
            "totalassignedtroops": 0,
            "transferplan": [],
            "targetprovinceids": [],
        }

    targetassignedlookup = {provinceid: 0 for provinceid in validtargetprovinceids}
    sourceamountlookup = {}
    for provinceid, province in sorted(provincemap.items()):
        if getprovincecontroller(province) != playercountry:
            continue
        assignedtroops = getprovincefrontlinetroops(province, frontlineid)
        if assignedtroops <= 0:
            continue
        if provinceid in targetprovinceidset:
            targetassignedlookup[provinceid] += assignedtroops
        sourceamountlookup[provinceid] = sourceamountlookup.get(provinceid, 0) + assignedtroops

    totalavailabletroops = sum(sourceamountlookup.values())
    if totalavailabletroops <= 0:
        return {
            "totalassignedtroops": 0,
            "transferplan": [],
            "targetprovinceids": [],
        }

    targetcount = len(validtargetprovinceids)
    baseallocation = totalavailabletroops // targetcount
    remainder = totalavailabletroops % targetcount
    desiredlookup = {
        provinceid: baseallocation + (1 if index < remainder else 0)
        for index, provinceid in enumerate(validtargetprovinceids)
    }

    transferplan = []
    movablelookup = {}
    projectedtargetlookup = dict(targetassignedlookup)
    for provinceid, assignedtroops in sourceamountlookup.items():
        if provinceid not in targetprovinceidset:
            movablelookup[provinceid] = assignedtroops
            continue

        province = provincemap.get(provinceid)
        tolerance = 4 if isprovinceentrenched(province, currentturnnumber) else 1
        desiredtroops = desiredlookup.get(provinceid, 0)
        keepamount = min(assignedtroops, desiredtroops + tolerance)
        if keepamount > 0:
            transferplan.append(
                {
                    "sourceprovinceid": provinceid,
                    "targetprovinceid": provinceid,
                    "amount": keepamount,
                }
            )
        movabletroops = assignedtroops - keepamount
        if movabletroops > 0:
            movablelookup[provinceid] = movabletroops
            projectedtargetlookup[provinceid] = keepamount

    for sourceprovinceid, availabletroops in movablelookup.items():
        assignedbytarget = {}
        remainingtroops = availabletroops
        while remainingtroops > 0:
            deficitprovinceids = [
                provinceid
                for provinceid in validtargetprovinceids
                if projectedtargetlookup.get(provinceid, 0) < desiredlookup.get(provinceid, 0)
            ]
            if deficitprovinceids:
                targetprovinceid = min(
                    deficitprovinceids,
                    key=lambda provinceid: (
                        projectedtargetlookup.get(provinceid, 0) - desiredlookup.get(provinceid, 0),
                        str(provinceid),
                    ),
                )
            else:
                targetprovinceid = min(
                    validtargetprovinceids,
                    key=lambda provinceid: (projectedtargetlookup.get(provinceid, 0), str(provinceid)),
                )
            assignedbytarget[targetprovinceid] = assignedbytarget.get(targetprovinceid, 0) + 1
            projectedtargetlookup[targetprovinceid] = projectedtargetlookup.get(targetprovinceid, 0) + 1
            remainingtroops -= 1

        for targetprovinceid, amount in assignedbytarget.items():
            transferplan.append(
                {
                    "sourceprovinceid": sourceprovinceid,
                    "targetprovinceid": targetprovinceid,
                    "amount": amount,
                }
            )

    totalassignedtroops = sum(entry["amount"] for entry in transferplan)
    targetprovinceids = [
        provinceid
        for provinceid in validtargetprovinceids
        if projectedtargetlookup.get(provinceid, 0) > 0
    ]
    return {
        "totalassignedtroops": totalassignedtroops,
        "transferplan": transferplan,
        "targetprovinceids": targetprovinceids,
    }


def orderfrontlineprovinceids(frontlineprovinceids, anchorprovinceid):
    orderedprovinceids = sorted(set(frontlineprovinceids or ()))
    if anchorprovinceid in orderedprovinceids:
        orderedprovinceids.remove(anchorprovinceid)
        orderedprovinceids.insert(0, anchorprovinceid)
    return orderedprovinceids


def buildfrontlineedges(
    provincemap,
    provincegraph,
    playercountry,
    frontlineprovinceids,
    anchorprovinceid,
    targetcountry=None,
    fallbackforeignprovinceid=None,
):
    frontlineedgekeys = set()
    frontlineedgelist = []

    for playerprovinceid in frontlineprovinceids:
        for foreignprovinceid in provincegraph.get(playerprovinceid, ()):
            foreignprovince = provincemap.get(foreignprovinceid)
            if not foreignprovince:
                continue

            foreigncountry = getprovincecontroller(foreignprovince)
            if foreigncountry == playercountry:
                continue
            if targetcountry is not None and foreigncountry != targetcountry:
                continue

            playerprovince = provincemap.get(playerprovinceid)
            if not playerprovince:
                continue
            sharedsegments = getsharedbordersegments(playerprovince, foreignprovince)
            if not sharedsegments:
                continue

            edgekey = getborderedgekey(playerprovinceid, foreignprovinceid)
            if edgekey in frontlineedgekeys:
                continue

            frontlineedgekeys.add(edgekey)
            frontlineedgelist.append(
                {
                    "playerprovinceid": playerprovinceid,
                    "foreignprovinceid": foreignprovinceid,
                    "edgekey": edgekey,
                    "foreigncountry": foreigncountry,
                    "worldsegments": sharedsegments,
                }
            )

    if not frontlineedgekeys and fallbackforeignprovinceid:
        fallbackedgekey = getborderedgekey(anchorprovinceid, fallbackforeignprovinceid)
        frontlineedgekeys.add(fallbackedgekey)
        frontlineedgelist.append(
            {
                "playerprovinceid": anchorprovinceid,
                "foreignprovinceid": fallbackforeignprovinceid,
                "edgekey": fallbackedgekey,
            }
        )

    return frontlineedgekeys, frontlineedgelist


def registerfrontlineassignment(provincemap, frontlineid, transferplan):
    sourcedelta = {}
    for transferentry in transferplan or ():
        sourceprovinceid = transferentry.get("sourceprovinceid")
        amount = max(0, int(transferentry.get("amount", 0)))
        if not sourceprovinceid or amount <= 0:
            continue
        sourcedelta[sourceprovinceid] = sourcedelta.get(sourceprovinceid, 0) + amount

    for sourceprovinceid, amount in sourcedelta.items():
        sourceprovince = provincemap.get(sourceprovinceid)
        if not sourceprovince:
            continue
        availabletroops = getprovinceunassignedtroops(sourceprovince)
        if availabletroops <= 0:
            continue
        addprovincefrontlinetroops(sourceprovince, frontlineid, min(amount, availabletroops))


def applyfrontlinetransferplan(
    frontlineassignment,
    transferplan,
    provincemap,
    provincegraph,
    movementorderlist,
    emit=None,
    currentturnnumber=None,
):
    frontlineid = frontlineassignment.get("frontlineid")
    playercountry = frontlineassignment.get("country")
    routepreviewset = set()
    appliedtransferplan = []

    if not frontlineid or not playercountry:
        return {
            "routepreviewset": routepreviewset,
            "appliedtransferplan": appliedtransferplan,
            "orderscreated": 0,
        }

    allowedprovinceidset = {
        provinceid
        for provinceid, province in provincemap.items()
        if getprovincecontroller(province) == playercountry
    }
    orderscreated = 0
    for transferentry in transferplan or ():
        sourceprovinceid = transferentry.get("sourceprovinceid")
        targetprovinceid = transferentry.get("targetprovinceid")
        transferamount = max(0, int(transferentry.get("amount", 0)))
        if not sourceprovinceid or not targetprovinceid or transferamount <= 0:
            continue

        sourceprovince = provincemap.get(sourceprovinceid)
        if not sourceprovince or getprovincecontroller(sourceprovince) != playercountry:
            continue

        availablefrontlinetroops = getprovincefrontlinetroops(sourceprovince, frontlineid)
        movingtroopcount = min(
            transferamount,
            availablefrontlinetroops,
            max(0, int(sourceprovince.get("troops", 0))),
        )
        if movingtroopcount <= 0:
            continue

        if sourceprovinceid == targetprovinceid:
            appliedtransferplan.append(
                {
                    "sourceprovinceid": sourceprovinceid,
                    "targetprovinceid": targetprovinceid,
                    "amount": movingtroopcount,
                }
            )
            continue

        foundpath = findprovincepath(
            sourceprovinceid,
            targetprovinceid,
            provincemap,
            provincegraph,
            allowedprovinceidset=allowedprovinceidset,
        )
        if len(foundpath) < 2:
            continue

        appliedtransferplan.append(
            {
                "sourceprovinceid": sourceprovinceid,
                "targetprovinceid": targetprovinceid,
                "amount": movingtroopcount,
            }
        )

        sourceprovince["troops"] -= movingtroopcount
        addprovincefrontlinetroops(sourceprovince, frontlineid, -movingtroopcount)
        markprovincetroopactivity(sourceprovince, currentturnnumber)
        movementorderlist.append(
            {
                "amount": movingtroopcount,
                "path": foundpath,
                "index": 0,
                "current": foundpath[0],
                "speedmodifier": 1.0,
                "controllercountry": getprovincecontroller(sourceprovince),
                "country": getprovincecontroller(sourceprovince),
                "countrycolor": sourceprovince.get("countrycolor"),
                "ordercreatedturn": currentturnnumber,
                "frontlineid": frontlineid,
                "divisionid": frontlineid,
            }
        )
        routepreviewset.update(foundpath)
        orderscreated += 1

        if emit is not None:
            emit(
                EngineEventType.MOVEORDERCREATED,
                {
                    "sourceProvinceId": sourceprovinceid,
                    "destinationProvinceId": targetprovinceid,
                    "path": list(foundpath),
                    "troops": movingtroopcount,
                    "country": getprovincecontroller(sourceprovince),
                    "turn": currentturnnumber,
                    "frontlineId": frontlineid,
                },
            )

    frontlineassignment["transferplan"] = appliedtransferplan
    return {
        "routepreviewset": routepreviewset,
        "appliedtransferplan": appliedtransferplan,
        "orderscreated": orderscreated,
    }


def autoadvancefrontlineassignment(
    frontlineassignment,
    provincemap,
    movementorderlist,
    emit=None,
    currentturnnumber=None,
    hostilecountryset=None,
):
    frontlineid = frontlineassignment.get("frontlineid")
    playercountry = frontlineassignment.get("country")
    if not frontlineid or not playercountry:
        return {
            "routepreviewset": set(),
            "orderscreated": 0,
        }

    frontlineedges = sorted(
        [edge for edge in frontlineassignment.get("frontlineedges", ()) if isinstance(edge, dict)],
        key=lambda edge: (
            str(edge.get("playerprovinceid", "")),
            str(edge.get("foreignprovinceid", "")),
        ),
    )
    if not frontlineedges:
        return {
            "routepreviewset": set(),
            "orderscreated": 0,
        }

    targetcountry = frontlineassignment.get("targetcountry")
    hostilecountryset = set(hostilecountryset) if hostilecountryset is not None else None
    maxorders = max(1, min(5, len(frontlineedges) // 2 + 1))
    routepreviewset = set()
    orderscreated = 0

    for edge in frontlineedges:
        if orderscreated >= maxorders:
            break

        sourceprovinceid = edge.get("playerprovinceid")
        targetprovinceid = edge.get("foreignprovinceid")
        if not sourceprovinceid or not targetprovinceid:
            continue

        sourceprovince = provincemap.get(sourceprovinceid)
        targetprovince = provincemap.get(targetprovinceid)
        if not sourceprovince or not targetprovince:
            continue
        if getprovincecontroller(sourceprovince) != playercountry:
            continue

        defendingcountry = getprovincecontroller(targetprovince)
        if not defendingcountry or defendingcountry == playercountry:
            continue
        if hostilecountryset is not None and defendingcountry not in hostilecountryset:
            continue
        if targetcountry and defendingcountry != targetcountry:
            continue

        availableassigned = min(
            getprovincefrontlinetroops(sourceprovince, frontlineid),
            max(0, int(sourceprovince.get("troops", 0))),
        )
        if availableassigned <= 1:
            continue

        defenders = max(0, int(targetprovince.get("troops", 0)))
        if defenders <= 0:
            minimumreserve = max(1, int(availableassigned * 0.35))
            requiredattackers = max(1, int(math.ceil(availableassigned * 0.45)))
        else:
            entrenched = isprovinceentrenched(targetprovince, currentturnnumber)
            defensemultiplier = entrenchmentdefensemultiplier if entrenched else 1.0
            effectivedefenders = int(math.ceil(defenders * defensemultiplier))
            requiredattackers = effectivedefenders + max(1, effectivedefenders // 4)
            minimumreserve = max(1, int(availableassigned * 0.30), defenders // 3)

        sparetroops = availableassigned - minimumreserve
        if sparetroops <= 0:
            continue
        if availableassigned < requiredattackers + minimumreserve:
            continue

        desiredattackers = max(
            requiredattackers,
            min(sparetroops, int(math.ceil(availableassigned * 0.45))),
        )
        movingtroopcount = min(sparetroops, max(desiredattackers, 1))
        if movingtroopcount <= 0:
            continue

        sourceprovince["troops"] -= movingtroopcount
        addprovincefrontlinetroops(sourceprovince, frontlineid, -movingtroopcount)
        markprovincetroopactivity(sourceprovince, currentturnnumber)
        path = [sourceprovinceid, targetprovinceid]
        movementorderlist.append(
            {
                "amount": movingtroopcount,
                "path": path,
                "index": 0,
                "current": sourceprovinceid,
                "speedmodifier": 1.0,
                "controllercountry": playercountry,
                "country": playercountry,
                "countrycolor": sourceprovince.get("countrycolor"),
                "ordercreatedturn": currentturnnumber,
                "frontlineid": frontlineid,
                "divisionid": frontlineid,
                "autoadvance": True,
            }
        )
        routepreviewset.update(path)
        orderscreated += 1

        if emit is not None:
            emit(
                EngineEventType.MOVEORDERCREATED,
                {
                    "sourceProvinceId": sourceprovinceid,
                    "destinationProvinceId": targetprovinceid,
                    "path": list(path),
                    "troops": movingtroopcount,
                    "country": playercountry,
                    "turn": currentturnnumber,
                    "frontlineId": frontlineid,
                    "autoAdvance": True,
                },
            )

    frontlineassignment["lastautoadvanceturn"] = currentturnnumber
    frontlineassignment["lastautoadvanceorders"] = orderscreated
    return {
        "routepreviewset": routepreviewset,
        "orderscreated": orderscreated,
    }


def refreshfrontlineassignment(
    frontlineassignment,
    provincemap,
    provincegraph,
    movementorderlist,
    emit=None,
    currentturnnumber=None,
):
    frontlineid = frontlineassignment.get("frontlineid")
    playercountry = frontlineassignment.get("country")
    if not frontlineid or not playercountry:
        frontlineassignment["active"] = False
        return {
            "success": False,
            "routepreviewset": set(),
        }

    normalizefrontlineassignments(provincemap)

    for province in provincemap.values():
        if getprovincecontroller(province) == playercountry:
            continue
        setprovincefrontlinetroops(province, frontlineid, 0)

    assignedstationarytroops = 0
    for province in provincemap.values():
        assignedstationarytroops += getprovincefrontlinetroops(province, frontlineid)
    assignedmovingtroops = sum(
        max(0, int(order.get("amount", 0)))
        for order in movementorderlist
        if order.get("frontlineid") == frontlineid
    )
    totaltroops = assignedstationarytroops + assignedmovingtroops
    if totaltroops <= 0:
        frontlineassignment["active"] = False
        frontlineassignment["assignedtroops"] = 0
        frontlineassignment["frontlineprovinceids"] = []
        frontlineassignment["frontlineedgekeys"] = set()
        frontlineassignment["frontlineedges"] = []
        frontlineassignment["transferplan"] = []
        return {
            "success": False,
            "routepreviewset": set(),
        }

    anchorprovinceid = frontlineassignment.get("anchorprovinceid")
    nearbydepth = max(1, int(frontlineassignment.get("nearbydepth", 2)))
    targetcountry = frontlineassignment.get("targetcountry")
    frontlineprovinceidset = getfrontlineprovinces(
        provincemap,
        provincegraph,
        playercountry,
        anchorprovinceid,
        targetcountry=targetcountry,
        nearbydepth=nearbydepth,
    )

    orderedfrontlineprovinceids = orderfrontlineprovinceids(frontlineprovinceidset, anchorprovinceid)
    if orderedfrontlineprovinceids and anchorprovinceid not in orderedfrontlineprovinceids:
        frontlineassignment["anchorprovinceid"] = orderedfrontlineprovinceids[0]
    elif not orderedfrontlineprovinceids:
        fallbackprovinceids = [
            provinceid
            for provinceid, province in sorted(provincemap.items())
            if getprovincefrontlinetroops(province, frontlineid) > 0
        ]
        orderedfrontlineprovinceids = fallbackprovinceids[:1]
        if orderedfrontlineprovinceids:
            frontlineassignment["anchorprovinceid"] = orderedfrontlineprovinceids[0]

    frontlineedgekeys, frontlineedges = buildfrontlineedges(
        provincemap,
        provincegraph,
        playercountry,
        orderedfrontlineprovinceids,
        frontlineassignment.get("anchorprovinceid"),
        targetcountry=targetcountry,
        fallbackforeignprovinceid=frontlineassignment.get("fallbackforeignprovinceid"),
    )

    transferplanresult = buildfrontlinedivisiontransferplan(
        provincemap,
        frontlineid,
        orderedfrontlineprovinceids,
        playercountry,
        currentturnnumber=currentturnnumber,
    )
    deploymentresult = applyfrontlinetransferplan(
        frontlineassignment,
        transferplanresult.get("transferplan", ()),
        provincemap,
        provincegraph,
        movementorderlist,
        emit=emit,
        currentturnnumber=currentturnnumber,
    )

    frontlineassignment["active"] = True
    frontlineassignment["assignedtroops"] = totaltroops
    frontlineassignment["frontlineprovinceids"] = orderedfrontlineprovinceids
    frontlineassignment["frontlineedgekeys"] = frontlineedgekeys
    frontlineassignment["frontlineedges"] = frontlineedges
    frontlineassignment["nearbydepth"] = nearbydepth
    return {
        "success": True,
        "routepreviewset": deploymentresult["routepreviewset"],
    }


def createfrontline(provincemap, provincegraph, playercountry, selectedprovinceids, borderedge, nearbydepth=2):

    if not borderedge:
        return {
            "success": False,
            "assignedtroops": 0,
            "frontlineprovinceids": [],
            "frontlineedgekeys": set(),
            "anchorprovinceid": None,
            "transferplan": [],
        }

    anchorprovinceid = borderedge.get("playerprovinceid")
    anchorprovince = provincemap.get(anchorprovinceid)



    if not anchorprovince or getprovincecontroller(anchorprovince) != playercountry:
        return {
            "success": False,
            "assignedtroops": 0,
            "frontlineprovinceids": [],
            "frontlineedgekeys": set(),
            "anchorprovinceid": None,
            "transferplan": [],
        }


    targetcountry = borderedge.get("foreigncountry")
    nearbyfrontlineprovinceidset = getfrontlineprovinces(
        provincemap,
        provincegraph,
        playercountry,
        anchorprovinceid,
        targetcountry=targetcountry,
        nearbydepth=nearbydepth,
    )
    if not nearbyfrontlineprovinceidset:
        nearbyfrontlineprovinceidset = {anchorprovinceid}

    frontlineprovinceids = orderfrontlineprovinceids(nearbyfrontlineprovinceidset, anchorprovinceid)

    frontlineplan = buildfrontlinetransferplan(
        provincemap,
        selectedprovinceids,
        frontlineprovinceids,
        playercountry,
    )
    assignedtroops = frontlineplan["totalassignedtroops"]
    assignedprovinceids = frontlineplan["targetprovinceids"]


    if assignedtroops <= 0 or not assignedprovinceids:
        return {
            "success": False,
            "assignedtroops": 0,
            "frontlineprovinceids": frontlineprovinceids,
            "frontlineedgekeys": set(),
            "anchorprovinceid": anchorprovinceid,
            "transferplan": [],
        }

    frontlineedgekeys, frontlineedgelist = buildfrontlineedges(
        provincemap,
        provincegraph,
        playercountry,
        assignedprovinceids,
        anchorprovinceid,
        targetcountry=targetcountry,
        fallbackforeignprovinceid=borderedge.get("foreignprovinceid"),
    )

    return {

        "success": True,
        "assignedtroops": assignedtroops,
        "frontlineprovinceids": assignedprovinceids,
        "frontlineedgekeys": frontlineedgekeys,
        "frontlineedges": frontlineedgelist,
        "anchorprovinceid": anchorprovinceid,
        "targetcountry": targetcountry,
        "country": playercountry,
        "nearbydepth": nearbydepth,
        "frontlineid": None,
        "divisionid": None,
        "divisionname": None,
        "autoadvance": False,
        "fallbackforeignprovinceid": borderedge.get("foreignprovinceid"),
        "active": True,
        "transferplan": frontlineplan["transferplan"],
    }


def pointtosegmentdistance(point, segmentstart, segmentend):
    pointx, pointy = point
    startx, starty = segmentstart
    endx, endy = segmentend

    segmentdx = endx - startx
    segmentdy = endy - starty
    segmentsquaredlength = segmentdx * segmentdx + segmentdy * segmentdy

    
    if segmentsquaredlength <= 1e-9:
        return math.hypot(pointx - startx, pointy - starty)

    projectionratio = ((pointx - startx) * segmentdx + (pointy - starty) * segmentdy) / segmentsquaredlength
    projectionratio = max(0.0, min(1.0, projectionratio))
    nearestx = startx + projectionratio * segmentdx
    nearesty = starty + projectionratio * segmentdy

    return math.hypot(pointx - nearestx, pointy - nearesty) # distnace from point to nearest point, hypotenuse




# Movement ends
