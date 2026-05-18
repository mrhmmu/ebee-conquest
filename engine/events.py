from collections import defaultdict
from enum import Enum #event type

 

class EngineEventType(str, Enum):
    WORLDLOADED = "worldloaded"

    COUNTRYCANDIDATESELECTED = "countrycandidateselected"
    PLAYERCOUNTRYSELECTED = "playercountryselected"
    STATESELECTED = "stateselected"
    PROVINCESELECTED = "provinceselected"

    MOVEORDERCREATED = "moveordercreated"
    MOVEORDERFINISHED = "moveorderfinished"
    COMBATRESOLVED = "combatresolved"
    PROVINCECONTROLCHANGED = "provincecontrolchanged"

    NEXTTURN = "nextturn"
    WARDECLARED = "wardeclared"
    TROOPSRECRUITED = "troopsrecruited"
    FOCUSSTARTED = "focusstarted"
    FOCUSCOMPLETED = "focuscompleted"
    CAPITULATED = "capitulated"


# main event handling 

class EventBus:

    def __init__(self):
        self.subscribers = defaultdict(list)

    @staticmethod
    def eventkey(eventname):
        if isinstance(eventname, EngineEventType):
            return eventname.value
        return str(eventname)



    def subscribe(self, eventname, callback):
        key = self.eventkey(eventname)
        self.subscribers[key].append(callback)
        return callback




    def unsubscribe(self, eventname, callback):
        key = self.eventkey(eventname)
        callbacklist = self.subscribers.get(key, [])
        if callback in callbacklist:
            callbacklist.remove(callback)
            return True
        return False



    def emit(self, eventname, payload):
        key = self.eventkey(eventname)
        for callback in tuple(self.subscribers.get(key, ())):
            callback(payload)


