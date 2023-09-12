#!/usr/bin/env seiscomp-python
# -*- coding: utf-8 -*-

import sys
import traceback
from seiscomp import client, datamodel
from seiscomp.client import Protocol
from seiscomp.math import delazi_wgs84
from seiscomp.core import Time
from numpy import average
from seiscomp import io

# TO DO:
#
# - ADD 
#   - logging
#   - origin quality
#   - option --dump-config 
# 
# - Improve: 
#   - Use Amplitudes
#   - Check cluster and/or origin location corresponds to correct pick and unpicked station distribution 
#   - Check cluster and/or origin location corresponds to correct sorting of amplitude and/or time  
#   - Use locators
#   - FASTER ACCESS TO COORDINATES: CACHE ALL STATIONS FROM INVENTORY?    


class Cluster(object):
    
    def __init__(self, *picks):
        self.picks = [p for p in picks]

    def tmin( self ):
        return min([ pick.time().value() for pick in self.picks ])
    
    def time_min( self ):
        return [ pick.time().value() for pick in self.picks if pick.time().value() == self.tmin()][0]
    
    def tmax( self ):
        return max([ pick.time().value() for pick in self.picks ])
    
    def len( self ):
        return len( self.picks )
    
    def get_coordinates(self):            
        return [ [ pick.la, pick.lo, pick.el ] for pick in self.picks ] 

    def get_weights(self):
        # weight should not reach 0
        tmax = self.tmax()
        tnorm = float(self.tmax()-self.tmin())
        return [ float(tmax - pick.time().value())/tnorm+0.01 for pick in self.picks ] 
    
    def get_ids(self):

        mseedids = []
        for pick in self.picks:
            wfid = pick.waveformID()
            mseedid = '%s.%s' % ( str(wfid.networkCode()),
                                  str(wfid.stationCode()) )            
            mseedid += '.'+str(wfid.locationCode())
            mseedid += '.'+str(wfid.channelCode())
            mseedids += [mseedid]

        return mseedids
    

class PickListener(client.Application):

    def __init__(self, argc, argv):
        client.Application.__init__(self, argc, argv)
        self.setMessagingEnabled(True)
        self.setDatabaseEnabled(True, False)
        #self.setPrimaryMessagingGroup(Protocol.LISTENER_GROUP)
        self.setPrimaryMessagingGroup("LOCATION")
        self.addMessagingSubscription("PICK")
        self.setLoadStationsEnabled(True)
        self.setLoggingToStdErr(True)
        self.pick_buffer = []
        self.clusters = []

        # Config
        self.max_buffer_interval = 3*60*60. # A buffer of 3 hours in seconds
                
        self.max_pick_delay =   120.   #in seconds
        self.max_pick_distance = 50.   #in km
        self.min_pick_distance =  1.   #in km
        self.default_phase_type = 'P'

        self.min_released_clustered_picks = 2
        self.test = False                 # if True nothing get sent despite any other parameter
        self.release_todatabase = True    # if True origin go only to messaging system, not to db (no public ID) 
        self.release_cluster = True       # if True cluster is released as preliminary origin 
        self.release_location = False     # if True origin location is released

        self.enable_loc_clust = True      # Useful if sta code is the same for distant instrument with different location code
        self.enable_cha_clust = False     # Useful if chanel level has coordinates (not in SED) and loc code is the same for distant instrument 
        self.enable_same_id_clust = False # Useful if the same stream should contribute several time to origin       

        self.inputFile = None
        self.inputFormat = 'xml'
        self.outputFile = '/dev/stdout'
        self.playback = False


    def validateParameters(self):
        try:
            if client.Application.validateParameters(self) is False:
                return False

            if self.commandline().hasOption("fake"):
                self.release_todatabase = False

            if self.commandline().hasOption("test"):
                self.test = True
                self.setMessagingEnabled(False)
            

            if self.commandline().hasOption("playback"):
                self.playback = True

            try:
                self.inputFile = self.commandline().optionString("ep")
                self.test = True
                self.setMessagingEnabled(False)
            except RuntimeError:
                pass

            try:
                self.inputFormat = self.commandline().optionString("format")
            except RuntimeError:
                pass

            try:
                self.outputFile = self.commandline().optionString("output")
                self.test = True
            except RuntimeError:
                pass

            return True
        except Exception:
            traceback.print_exc()
            sys.exit(-1)

    def createCommandLineDescription(self):
        self.commandline().addGroup("Input")
        self.commandline().addStringOption(
            "Input", "ep",
            "read picks from XML file instead of messaging system. Use '-' to read "
            "from stdin.")
        self.commandline().addStringOption(
            "Input", "format,f",
            "input format to use (xml [default], zxml (zipped xml), binary). "
            "Only relevant with --ep.")
        self.commandline().addStringOption(
            "Input", "output,o",
            "write origins to specific XML file instead of stdout. "
            "Only relevant with --input.")
        self.commandline().addOption(
            "Input", "playback",
            "Release origins in real-time, similar to online processing, else "
            "release final origins only. Only relevant with --input.")
        self.commandline().addOption(
            "Messaging", "test",
            "Do not send any object.")
        self.commandline().addOption(
            "Messaging", "fake",
            "Do not write to database (do not create public id for sent object).")

        return True
    
    def initConfiguration(self):

        if not client.Application.initConfiguration(self):
            return False

        try:
            self.max_buffer_interval = self.configGetDouble("max_buffer_interval")
        except Exception as e:
            pass

        try:
            self.max_pick_delay = self.configGetDouble("max_pick_delay")
            print('max_pick_delay',self.max_pick_delay )
        except Exception as e:
            pass
        try:
            self.max_pick_distance = self.configGetDouble("max_pick_distance")
        except Exception as e:
            pass
        try:
            self.default_phase_type = self.configGetString("default_phase_type")
            print('default_phase_type',self.default_phase_type )
        except Exception as e:
            pass

        try:
            self.min_released_clustered_picks = self.configGetInt("min_released_clustered_picks")
        except Exception as e:
            pass
        try:
            self.test = self.configGetBool("test")
        except Exception as e:
            pass              
        try:
            self.release_todatabase = self.configGetBool("release_todatabase")
            print('release_todatabase',self.release_todatabase )
        except Exception as e:
            pass 
        try:
            self.release_cluster = self.configGetBool("release_cluster")
        except Exception as e:
            pass  
        try:
            self.release_location = self.configGetBool("release_location")
        except Exception as e:
            pass   

        try:
            self.enable_loc_clust = self.configGetBool("enable_loc_clust")
        except Exception as e:
            pass     
        try:
            self.enable_cha_clust = self.configGetBool("enable_cha_clust")
        except Exception as e:
            pass   
        try:
            self.enable_same_id_clust = self.configGetBool("enable_same_id_clust")
        except Exception as e:
            pass
        

        return True

    def handlePick(self, pick):
        try:
            self.buffer_add( pick )

            self.buffer_scan( )

            if self.playback or self.inputFile is None:
                self.origins_release()
            else:
                print('Skipping real-time origin release because options playback=%s or ep=%s'%(self.playback,self.inputFile))
            
        except Exception:
            traceback.print_exc()
            return

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
    
    def buffer_add(self, pick):

        if ( sta := self.pick2chan( pick ) ) is False :
            wfid = pick.waveformID()
            print('WARNING: STATION %s.%s NOT IN INVENTORY'%(str(wfid.networkCode()),
                                                             str(wfid.stationCode())))
            return
        
        pick.la = sta['la']
        pick.lo = sta['lo']
        pick.el = sta['el']
        self.pick_buffer += [ pick ]
        
        print('min %s max %s len %d'%(self.buffer_min(),self.buffer_max(), self.buffer_len()))

        if float( self.buffer_max() - self.buffer_min() )  > self.max_buffer_interval :
            to_pop = []
            for pick in self.pick_buffer:
                if float( self.buffer_max() - pick.time().value() )  > self.max_buffer_interval:
                    to_pop += [ pick ]

            for pick in to_pop:
                print("removed: {}".format(pick.publicID()))
                self.pick_buffer.remove(pick)
        
        print('in buffer for {}:'.format(pick.time().value(),))
        print('min %s max %s len %d'%(self.buffer_min(),self.buffer_max(), self.buffer_len()))
        
        to_pop = []
        for c in self.clusters:
            if float( self.buffer_max() - c.tmax() ) > self.max_buffer_interval :
                # OUTDATED CLUSTER (endtime<buffer starttime)
                to_pop += [c]
        for c in to_pop:
            print("removed: cluster ending on {}".format(c.tmax()))
            self.clusters.remove(c)
    
    def is_staloccha_availableattime(self, staloccha, pick):

        try:
            start = staloccha.start()
        except Exception:
            return False 
        try:
            end = staloccha.end()
            if not start <= pick.time().value() <= end:
                return False 
        except Exception:
            return True   

        return True 
        
    def pick2chan(self, pick):
        wfid = pick.waveformID()

        print('%s.%s.%s.%s at %s'%( str(wfid.networkCode()),
                                    str(wfid.stationCode()),
                                    str(wfid.locationCode()),
                                    str(wfid.channelCode()),
                                    str(pick.time().value()) 
                                   ))
    
        try:   
            # USE https://github.com/SeisComP/main/blob/b591e0de56fa85434b60ba306ec4df794713a175/apps/python/sh2proc.py#L161 INSTEAD     OR
            # https://github.com/SeisComP/main/blob/b591e0de56fa85434b60ba306ec4df794713a175/apps/python/scevtstreams.py#L286 
            
            #self.dbr = datamodel.DatabaseReader(self.database())
            self.inv = client.Inventory.Instance().inventory()    
            #self.dbr.loadNetworks(self.inv)
            nnet = self.inv.networkCount()
            for inet in range(nnet):
                net = self.inv.network(inet)
                if str(net.code()) != str(wfid.networkCode()):
                    continue

                print("Network {:2} ".format(net.code()))                

                #self.dbr.load(net)
                nsta = net.stationCount()
                for ista in range(nsta):
                    sta = net.station(ista)
                    if str(sta.code()) != str(wfid.stationCode()):
                        continue

                    if not self.is_staloccha_availableattime( sta, pick ):   
                        continue         
                    
                    print("Station {:5} ".format(sta.code()))

                    #self.dbr.load(sta)
                    nloc = sta.sensorLocationCount()*self.enable_loc_clust
                    for iloc in range(nloc):
                        loc = sta.sensorLocation(iloc)
                        if str(loc.code()) != str(wfid.locationCode()):
                            continue
                        
                        if not self.is_staloccha_availableattime( loc, pick ):   
                            continue                           
                        
                        print("Location '{:2}' ".format(loc.code()))

                        #self.dbr.load(loc)
                        ncha = loc.streamCount()*self.enable_cha_clust 
                        for icha in range(ncha):
                            cha = loc.stream(icha)
                            if str(cha.code()) != str(wfid.channelCode()):
                                continue
                            
                            if not self.is_staloccha_availableattime( cha, pick ):   
                                continue                   

                            print("Channel {:3}".format(cha.code()))            
                               
                            if "latitude" in dir(cha) and "longitude" in dir(cha)  and "elevation" in dir(cha):                             
                                print("Channel: {:9.4f} {:9.4f} {:9.4f}".format(cha.latitude(), 
                                                                                cha.longitude(), 
                                                                                cha.elevation()))
                                
                                return {'la':cha.latitude(),
                                        'lo':cha.longitude(),
                                         'el':cha.elevation()}
                               
                        if "latitude" in dir(loc) and "longitude" in dir(loc) and "elevation" in dir(loc):                             
                            print("Location: {:9.4f} {:9.4f} {:9.4f}".format(loc.latitude(), 
                                                                             loc.longitude(), 
                                                                             loc.elevation()))
                            
                            return {'la':loc.latitude(),
                                    'lo':loc.longitude(),
                                    'el':loc.elevation()}
                    
                    if "latitude" in dir(sta) and "longitude" in dir(sta) and "elevation" in dir(sta):                             
                        print("Station: {:9.4f} {:9.4f} {:9.4f}".format(sta.latitude(), 
                                                                        sta.longitude(), 
                                                                        sta.elevation()))
                        
                        return {'la':sta.latitude(),
                                'lo':sta.longitude(),
                                'el':sta.elevation()}

        except Exception:
            traceback.print_exc()
            sys.exit(-1)
        
        return False

    def buffer_min(self):
        return min([ pick.time().value() for pick in self.pick_buffer ])
    def buffer_max(self):
        return max([ pick.time().value() for pick in self.pick_buffer ])
    def buffer_len(self):
        return len( self.pick_buffer )
    
    def mseedid(self,pick):

        wfid = pick.waveformID()

        mseedid = '%s.%s'%( str(wfid.networkCode()),
                                str(wfid.stationCode()))
        
        if self.enable_loc_clust :
            mseedid += '.'+str(wfid.locationCode())
        
        if self.enable_cha_clust :
            mseedid += '.'+str(wfid.channelCode())

        return mseedid
            

    def buffer_scan(self):
        
        self.release = []
        for p1,pick1 in enumerate(self.pick_buffer):
            for p2,pick2 in enumerate(self.pick_buffer):

                if p2==p1:
                    #SAME PICK
                    break
                
                mseedid1 = self.mseedid(pick1)
                mseedid2 = self.mseedid(pick2)

                if mseedid1 == mseedid2 and not self.enable_same_id_clust:
                    # SAME NET, STAT (, LOC (,CHA))
                    continue

                # check if picks are already clustered
                pick1clust = [ c for c,clust in enumerate(self.clusters) if pick1 in clust.picks ]
                pick2clust = [ c for c,clust in enumerate(self.clusters) if pick2 in clust.picks ]

                if len(pick2clust)>1 or len(pick1clust)>1:
                    print('WARNING PICKS DUPLICATED IN CLUSTERS')
                if len(pick2clust) and len(pick1clust):
                    continue # both already clustered


                # check pick times similarity
                dt = float( pick1.time().value() - pick2.time().value() )
                if abs(dt) > self.max_pick_delay:
                    continue

                # check pick locations distance
                elat = pick1.la
                elon = pick1.lo
                slat = pick2.la
                slon = pick2.lo
                delta = delazi_wgs84(elat, elon, slat, slon)[0] * 110.0
                if delta > self.max_pick_distance:
                    continue
                if  delta < self.min_pick_distance:
                    continue

                
                # Add picks into clusters
                if len(pick1clust) and not len(pick2clust):
                    # check if mseedid are already in clust
                    if not self.enable_same_id_clust and mseedid2 in [ self.mseedid(p) for p in self.clusters[pick1clust[0]].picks ]:
                        print(mseedid2, 'already in cluster', pick1clust[0] )
                        continue

                    print('Upgrading cluster {} '.format(pick1clust[0]))
                    print('With', mseedid2)
                    self.clusters[pick1clust[0]].picks += [ pick2 ]
                    self.release += [ pick1clust[0] ]

                elif len(pick2clust) and not len(pick1clust):
                    # check if mseedid are already in clust
                    if not self.enable_same_id_clust and mseedid1 in [ self.mseedid(p) for p in self.clusters[pick2clust[0]].picks ]:
                        print(mseedid1, 'already in cluster', pick2clust[0] )
                        continue

                    print('Upgrading cluster {} '.format(pick2clust[0]))
                    print('With', mseedid1)
                    self.clusters[pick2clust[0]].picks += [ pick1 ]
                    self.release += [ pick2clust[0] ]

                else:
                    print('New cluster')
                    print('With both', mseedid1, 'and', mseedid2)
                    self.clusters += [ Cluster( pick1, pick2 ) ]
                    self.release += [ len(self.clusters)-1 ]

                print(mseedid1, 'versus', mseedid2)
                print(dt,'=',str(pick1.time().value()),"-",str(pick2.time().value()))
                print(delta ,'= delazi_wgs84(',elat, elon, slat, slon,")")

        self.release = list(set(self.release))
        print('.'.join(['Cluster #%d: %d picks'%(i,c.len()) for i,c in enumerate(self.clusters)]))
        print('Cluster(s) to release: #%s'%', #'.join(['%d'%i for i in self.release]))

    def origins_release(self):        

        for c in self.release:
            
            cluster = self.clusters[c]

            # Get average of those centroids, weighted by the signed areas.
            latlonel = average(cluster.get_coordinates(), 
                               axis=0, 
                               weights=cluster.get_weights()
                               )
            latlonel[2] /= -1000.
            origin = self.make_origin(*latlonel, 
                                      cluster.time_min(), 
                                      cluster.picks, 
                                      cluster.get_weights())
            
            origin.setMethodID('weighted average')
            origin.setType(datamodel.CENTROID)

            print('Origin (weighted average centroid):')
            print('  ',latlonel[0],'°N', latlonel[1],'°E', latlonel[2],'km bsl at', cluster.time_min())
            print('   picks mseedids:', cluster.get_ids())
            print('   picks weigths:', cluster.get_weights())
            print('   picks (lat,lon,el):', cluster.get_coordinates())

            if self.release_cluster :
                #release origin with cluster release
                self.send_origin( origin )

            if self.release_location :
                #release origin with located cluster
                # https://github.com/SeisComP/scdlpicker/blob/ad7354f18034a3ea8a4af65c7067a67cddb2aaa5/lib/relocation.py#L89
                # https://github.com/swiss-seismological-service/sed-SeisComP-contributions/blob/6014f671a85ad4a69d3b3380e1abfcabf10c9d17/apps/screloc/main.cpp#L170C26-L170C41
                self.send_origin( origin )

    def make_origin(self, lat, lon, dep, time, picks, weightpicks):

        origin = datamodel.Origin.Create()

        ci = datamodel.CreationInfo()
        ci.setAgencyID(self.agencyID())
        ci.setCreationTime(Time.GMT())
        ci.setAuthor(self.author())
        ci.setModificationTime(Time.GMT())
        origin.setCreationInfo(ci)

        origin.setLongitude(datamodel.RealQuantity(lon))
        origin.setLatitude(datamodel.RealQuantity(lat))
        origin.setDepth(datamodel.RealQuantity(dep))
        origin.setTime(datamodel.TimeQuantity(time))
        origin.setEvaluationMode(datamodel.AUTOMATIC)
        origin.setEvaluationStatus(datamodel.PRELIMINARY)

        for p,pick in enumerate(picks):
                phase = datamodel.Phase()
                phase.setCode(self.default_phase_type)
                arr = datamodel.Arrival()
                arr.setPhase(phase)
                arr.setPickID(pick.publicID())
                arr.setTimeUsed(True)
                arr.setWeight(weightpicks[p])
                origin.add(arr)
                print(pick.publicID(), "added")
        
        oq = datamodel.OriginQuality()
        oq.setAssociatedPhaseCount(len(picks))
        oq.setUsedPhaseCount(len(picks))
        #oq.setAssociatedStationCount()
        #oq.setUsedStationCount()
        #oq.setAzimuthalGap()
        #oq.setSecondaryAzimuthalGap()
        #oq.setMaximumDistance()
        #oq.setMinimumDistance()
        #oq.setMedianDistance()
        #oq.setStandardError()#RMS of the travel time residuals of the arrivals used for the origin computation in seconds.
        origin.setQuality(oq)
        
        return origin


    def send_origin(self, origin):
        
        if self.inputFile is not None:
            self.ep = datamodel.EventParameters()
            self.ep.add(origin)
            return True

        if self.release_todatabase:
            if False:
                msg = datamodel.NotifierMessage()
                n = datamodel.Notifier("EventParameters",datamodel.OP_ADD, origin)
                msg.attach(n)
            else:
                self.ep = datamodel.EventParameters()
                datamodel.Notifier.Enable()
                self.ep.add(origin)
                msg = datamodel.Notifier.GetMessage()
                datamodel.Notifier.Disable()
            
        else:
            msg = datamodel.ArtificialOriginMessage(origin)
        
        if not self.test:
            if self.connection().send(msg):
                print("sent origin")# + origin.publicID()) #seiscomp.logging.info
            else:
                print("WARNING failed to send")# + origin.publicID()) #seiscomp.logging.info
        else:
            print('TEST MODE, ORIGIN NOT SENT')        

        return True
    
    def readXML(self):

        if self.inputFormat == "xml":
            ar = io.XMLArchive()
        elif self.inputFormat == "zxml":
            ar = io.XMLArchive()
            ar.setCompression(True)
        elif self.inputFormat == "binary":
            ar = io.VBinaryArchive()
        else:
            raise TypeError("unknown input format '{}'".format(
                self.inputFormat))

        if not ar.open(self.inputFile):
            raise IOError("unable to open input file")

        obj = ar.readObject()
        if obj is None:
            raise TypeError("invalid input file format")

        ep = datamodel.EventParameters.Cast(obj)
        if ep is None:
            raise ValueError("no event parameters found in input file")

        # we require at least one origin which references to magnitude
        if ep.pickCount() == 0:
            raise ValueError("no pick found in input file")

        pickIDs = []
        # no event, use all available picks
        for i in range(ep.pickCount()):
            pickIDs += [ep.pick(i).publicID()]

        # collect picks
        picks = []
        for pID in pickIDs:
            p = datamodel.Pick.Find(pID)
            if p is None:
                continue
            picks.append(p)
            if len(picks)>5:
                break

        return picks
    
    def run(self):

        # read picks from input file
        if self.inputFile:
            picks = self.readXML()
            if not picks:
                raise ValueError("Could not find picks in input file")
            for pick in picks:
                self.handlePick(pick)    
            
            if not self.playback :
                # not cluster location released in real-time yet, release needed
                self.origins_release()

            ar = io.XMLArchive()
            ar.create(self.outputFile)
            ar.setFormattedOutput(True)
            ar.writeObject(self.ep)            
            ar.close()
            return True
            
        print("Hi! The pick listener is now running.")
        return client.Application.run(self)


def main():
    app = PickListener(len(sys.argv), sys.argv)
    return app()


if __name__ == "__main__":
    sys.exit(main())