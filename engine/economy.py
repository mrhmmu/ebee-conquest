from .movement import getprovincecontroller
#PLEASE PUT ANYTHING RLEATED TO ECONOMY IN HERE

#PLACEHOLDER, EACH COUNTRY WILL HAVE THEIR OWN ECONOMY CONFIG LATER
defaulteconomy = {
    "startinggold": 1200,
    "startingpopulation": 2500,
    "startingstability": 50.0,
    "startingpp": 200,
    "startingap": 100,
    "recruitamount": 100,
    "recruitgoldcostperunit": 1,
    "recruitpopulationcostperunit": 1,
    "mingoldincome": 5,
    "goldincomedivisor": 5,
    "minpopulationgrowth": 10,
    "populationgrowthdivisor": 3,
    "populationgrowthbonus": 0,
    "stabilitychangemin": -1,
    "stabilitychangemax": 2,
    "stabilitydivisor": 8,
    "ppincome": 10,
    "ppincomedivisor": 4,
    "apincome": 20,
    "apincomedivisor": 3,
    "declarewarcost": 75,
    "moveorderapcost": 10,
}


def getdefaulteconomyconfig():
    return dict(defaulteconomy)




def initializeplayereconomy(economyconfig=None):

    config = economyconfig or defaulteconomy

    return (
        config["startinggold"],
        config["startingpopulation"],
        config["startingstability"],
        config["startingpp"],
        config["startingap"],
        config["recruitamount"],
        config["recruitgoldcostperunit"],
        config["recruitpopulationcostperunit"],
    )


def getendturneconomydelta(ownedprovincecount, economyconfig=None):

    config = economyconfig or defaulteconomy
    goldincome = max(config["mingoldincome"], ownedprovincecount // config["goldincomedivisor"])
    populationgrowth = max(config["minpopulationgrowth"], ownedprovincecount // config["populationgrowthdivisor"])
    populationgrowth += int(config.get("populationgrowthbonus", 0) or 0)
    populationgrowth = max(0, populationgrowth)

    stabilitydelta = ownedprovincecount // config.get("stabilitydivisor", 8)
    stabilitydelta = max(config.get("stabilitychangemin", -1), min(config.get("stabilitychangemax", 2), stabilitydelta))

    ppincome = max(5, ownedprovincecount // config.get("ppincomedivisor", 4))
    ppincome = min(config.get("ppincome", 10), ppincome)

    apincome = max(10, ownedprovincecount // config.get("apincomedivisor", 3))
    apincome = min(config.get("apincome", 20), apincome)

    return goldincome, populationgrowth, stabilitydelta, ppincome, apincome


def getrecruitcosts(recruitamount, recruitgoldcostperunit, recruitpopulationcostperunit):

    
    requiredgold = recruitamount * recruitgoldcostperunit
    requiredpopulation = recruitamount * recruitpopulationcostperunit

    return requiredgold, requiredpopulation




def canrecruittroops(playergold, playerpopulation, requiredgold, requiredpopulation, developmentmode=False):
    if developmentmode:
        return True
    
    return playergold >= requiredgold and playerpopulation >= requiredpopulation


def applyendturneconomy(playercountry, provincemap, playergold, playerpopulation, playerstability, playerpp, playerap):
    if not playercountry:

        return playergold, playerpopulation, playerstability, playerpp, playerap

    ownedprovincecount = sum(
        1 for province in provincemap.values() if getprovincecontroller(province) == playercountry
    )


    goldincome, populationgrowth, stabilitydelta, ppincome, apincome = getendturneconomydelta(ownedprovincecount)
    playergold += goldincome
    playerpopulation += populationgrowth
    playerstability = max(0.0, min(100.0, playerstability + stabilitydelta))
    playerpp += ppincome
    playerap += apincome

    return playergold, playerpopulation, playerstability, playerpp, playerap
