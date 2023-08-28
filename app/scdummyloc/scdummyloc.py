#!/usr/bin/env seiscomp-python
# -*- coding: utf-8 -*-

import sys
import traceback
from seiscomp import client, datamodel
from seiscomp.client import Protocol


class PickListener(client.Application):

    def __init__(self, argc, argv):
        client.Application.__init__(self, argc, argv)
        self.setMessagingEnabled(True)
        self.setDatabaseEnabled(False, False)
        self.setPrimaryMessagingGroup(Protocol.LISTENER_GROUP)
        self.addMessagingSubscription("PICK")
        self.setLoggingToStdErr(True)

    def handlePick(self, pick):
        try:
            #################################
            # Include your custom code here #
            print("pick.publicID = {}".format(pick.publicID()))
            #################################
        except Exception:
            traceback.print_exc()
            return
        
        self.pick_buffer += [pick]

    def updateObject(self, parentID, scobject):
        # called if an updated object is received
        pick = datamodel.Pick.Cast(scobject)
        if pick:
            print("received update for pick {}".format(pick.publicID()))
            self.handlePick(pick)

    def addObject(self, parentID, scobject):
        # called if a new object is received
        pick = datamodel.Pick.Cast(scobject)
        if pick:
            print("received new pick {}".format(pick.publicID()))
            self.handlePick(pick)

    def run(self):
        self.pick_buffer = []
        print("Hi! The pick listener is now running.")
        return client.Application.run(self)


def main():
    app = PickListener(len(sys.argv), sys.argv)
    return app()


if __name__ == "__main__":
    sys.exit(main())