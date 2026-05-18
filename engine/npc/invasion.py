from ..movement import findprovincepath, getprovincecontroller
# INVASION PLANNER 


class NpcInvasionPlanner:
    def __init__(
        self,
        provincemap,
        provincegraph,
        economyconfig,
        countryindex,
        strengthevaluator,
        actionwriter,
        invasiongarrison,
        maxinvasionordersperturn,
        maxinvasiontargetsperenemy,
        attritionattackthresholdratio,
        attritionattackcommitratio,
    ):
        self.provincemap = provincemap if provincemap is not None else {}
        self.provincegraph = provincegraph if provincegraph is not None else {}
        self.economyconfig = economyconfig
        self.countryindex = countryindex
        self.strengthevaluator = strengthevaluator
        self.actionwriter = actionwriter
        self.invasiongarrison = invasiongarrison
        self.maxinvasionordersperturn = maxinvasionordersperturn
        self.maxinvasiontargetsperenemy = maxinvasiontargetsperenemy
        self.attritionattackthresholdratio = attritionattackthresholdratio
        self.attritionattackcommitratio = attritionattackcommitratio

    def buildattackplans(self, countryname, sourceprovinceids, targetprovinceid, allowedprovinceidset, pathcache):
        attackplanlist = []
        for sourceprovinceid in sourceprovinceids:
            sourceprovince = self.provincemap[sourceprovinceid]
            sourcetroops = int(sourceprovince.get("troops", 0))
            movabletroops = sourcetroops - self.invasiongarrison
            if movabletroops <= 0:
                continue

            pathkey = (sourceprovinceid, targetprovinceid)
            path = pathcache.get(pathkey)
            if path is None:
                path = findprovincepath(
                    sourceprovinceid,
                    targetprovinceid,
                    self.provincemap,
                    self.provincegraph,
                    allowedprovinceidset=allowedprovinceidset,
                )
                pathcache[pathkey] = path
            if len(path) < 2:
                continue

            attackplanlist.append(
                {
                    "sourceProvinceId": sourceprovinceid,
                    "path": path,
                    "troops": movabletroops,
                }
            )

        attackplanlist.sort(
            key=lambda entry: (
                len(entry["path"]),
                -entry["troops"],
                entry["sourceProvinceId"],
            )
        )
        return attackplanlist

    def enemyinvasionlimits(self, warenemycount, enemyaggression):
        totalorderlimit = max(
            self.maxinvasionordersperturn * max(1, warenemycount),
            warenemycount * max(2, self.maxinvasiontargetsperenemy) * 3,
        )
        enemyorderlimit = max(2, int(self.maxinvasionordersperturn * enemyaggression))
        return totalorderlimit, enemyorderlimit

    def targetcountlimit(self, targetprovinceids, enemyaggression):
        return max(
            self.maxinvasiontargetsperenemy,
            min(
                len(targetprovinceids),
                max(2, int(len(targetprovinceids) * (0.55 + 0.35 * enemyaggression))),
            ),
        )

    def shouldskipattritionattack(
        self,
        totalattackers,
        defendercount,
        enemyaggression,
        targetisentrenched,
    ):
        effectiveattritionthreshold = max(
            0.45,
            self.attritionattackthresholdratio - ((enemyaggression - 1.0) * 0.25),
        )
        if targetisentrenched:
            # entrenched targets allow earlier attrition pressure.
            effectiveattritionthreshold = min(effectiveattritionthreshold, 0.30)
        minimumattritionforce = max(1, int(defendercount * effectiveattritionthreshold))
        return totalattackers < minimumattritionforce

    def assaulttroopgoal(
        self,
        totalattackers,
        defendercount,
        enemyaggression,
        targetisentrenched,
        hasfreshdefenderdrop,
    ):
        cancapture = totalattackers > defendercount
        bonuscapturecommitratio = 1.0 + max(0.0, min(0.65, (enemyaggression - 1.0) * 0.4))
        if cancapture:
            troopssendneeded = max(
                defendercount + 1,
                int(defendercount * bonuscapturecommitratio) + 1,
            )
            return min(totalattackers, max(1, troopssendneeded))

        # avoid instant opportunistic attacks after a same-turn defender drop.
        if hasfreshdefenderdrop:
            return None
        if self.shouldskipattritionattack(totalattackers, defendercount, enemyaggression, targetisentrenched):
            return None

        effectivecommitratio = min(
            1.35,
            self.attritionattackcommitratio + ((enemyaggression - 1.0) * 0.2),
        )
        if targetisentrenched:
            effectivecommitratio = min(1.5, effectivecommitratio + 0.12)
        targetassaultforce = max(1, int(defendercount * effectivecommitratio))
        troopssendneeded = min(totalattackers, targetassaultforce)
        return min(totalattackers, max(1, troopssendneeded))

    def attackwavesize(self, defendercount, enemyaggression):
        recruitamount = int(self.economyconfig.get("recruitamount", 100))
        return max(
            1,
            int(max(recruitamount // 2, defendercount * (0.35 + (enemyaggression - 1.0) * 0.15))),
        )

    def issueattackwaves(
        self,
        countryname,
        attackplanlist,
        troopssendneeded,
        defendercount,
        enemyaggression,
        movementorderlist,
        turnnumber,
        orderscreated,
        enemyorderscreated,
        invasionorderlimit,
        enemyorderlimit,
    ):
        wavesizebase = self.attackwavesize(defendercount, enemyaggression)
        for attackplan in attackplanlist:
            if (
                orderscreated >= invasionorderlimit
                or enemyorderscreated >= enemyorderlimit
                or troopssendneeded <= 0
            ):
                break

            sourceprovinceid = attackplan["sourceProvinceId"]
            sourceprovince = self.provincemap[sourceprovinceid]
            sourcetroops = int(sourceprovince.get("troops", 0))
            movabletroops = sourcetroops - self.invasiongarrison
            if movabletroops <= 0:
                continue

            movingtroops = min(movabletroops, max(1, min(troopssendneeded, wavesizebase)))
            self.actionwriter.movetrooporder(
                movementorderlist,
                countryname,
                sourceprovinceid,
                attackplan["path"],
                movingtroops,
                turnnumber,
            )
            orderscreated += 1
            enemyorderscreated += 1
            troopssendneeded -= movingtroops

        return orderscreated, enemyorderscreated


    # TODO: Prioritize invasion targets based on strategic value, such as proximity to the capital or valuable resources, or based on personality traits or current war status. Also consider adding logic for deciding when to pull forces from the frontline to reinforce reserves or other provinces, or when to counterattack invading forces instead of just reinforcing the frontline.
    # THIS IS FOR PLANNING OFFENSIVE MOVEMENT FOR AN INVASION, NOT FOR REACTING TO AN INVASION!! REACTIVE DEFENSIVE MOVEMENT LOGIC SHOULD GO IN NPCDEFENSEPLANNER
    def invadecountry(self, countryname, warlookup, movementorderlist, turnnumber, personality=None):
        warenemyset = sorted(set(warlookup.get(countryname, set())))
        if not warenemyset:
            return 0

        # eso: cache allowed conflict sets and target paths per enemy.
        orderscreated = 0
        sourceprovinceids = self.countryindex.controlledprovinceids(countryname)
        allowedsetcache = {}
        for enemycountry in warenemyset:
            enemyaggression = self.strengthevaluator.enemyaggression(
                countryname,
                enemycountry,
                personality=personality,
            )
            invasionorderlimit, enemyorderlimit = self.enemyinvasionlimits(len(warenemyset), enemyaggression)
            if orderscreated >= invasionorderlimit:
                break
            enemyorderscreated = 0

            allowedprovinceidset = allowedsetcache.get(enemycountry)
            if allowedprovinceidset is None:
                allowedprovinceidset = {
                    provinceid
                    for provinceid, province in self.provincemap.items()
                    if getprovincecontroller(province) in {countryname, enemycountry}
                }
                allowedsetcache[enemycountry] = allowedprovinceidset
            pathcache = {}

            targetprovinceids = self.countryindex.enemybordertargetids(countryname, enemycountry)
            if not targetprovinceids:
                continue

            targetcountlimit = self.targetcountlimit(targetprovinceids, enemyaggression)
            prioritizedtargetids = sorted(
                targetprovinceids,
                key=lambda provinceid: (
                    self.strengthevaluator.estimateddefenders(provinceid),
                    provinceid,
                ),
            )[:targetcountlimit]

            for targetprovinceid in prioritizedtargetids:
                if orderscreated >= invasionorderlimit or enemyorderscreated >= enemyorderlimit:
                    break

                attackplanlist = self.buildattackplans(
                    countryname,
                    sourceprovinceids,
                    targetprovinceid,
                    allowedprovinceidset,
                    pathcache,
                )
                if not attackplanlist:
                    continue

                defendercount = self.strengthevaluator.estimateddefenders(targetprovinceid)
                targetisentrenched = self.strengthevaluator.targetentrenched(targetprovinceid)
                currentdefendercount = int(self.provincemap[targetprovinceid].get("troops", 0))
                previousrawdefendercount = int(
                    self.strengthevaluator.provincetroopsintel.get(
                        targetprovinceid,
                        currentdefendercount,
                    )
                )
                hasfreshdefenderdrop = currentdefendercount < previousrawdefendercount
                totalattackers = sum(plan["troops"] for plan in attackplanlist)

                troopssendneeded = self.assaulttroopgoal(
                    totalattackers,
                    defendercount,
                    enemyaggression,
                    targetisentrenched,
                    hasfreshdefenderdrop,
                )
                if troopssendneeded is None:
                    continue

                orderscreated, enemyorderscreated = self.issueattackwaves(
                    countryname,
                    attackplanlist,
                    troopssendneeded,
                    defendercount,
                    enemyaggression,
                    movementorderlist,
                    turnnumber,
                    orderscreated,
                    enemyorderscreated,
                    invasionorderlimit,
                    enemyorderlimit,
                )

        return orderscreated
