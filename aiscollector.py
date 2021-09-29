#!/usr/bin/python
# aiscollector.py read ais messages, collect (compress) over some time, send to aprs.fi (json) and marinetraffic.com
# version 0.4
# Author: dj8kl@dj8kl.de 2021-09-16
#
# this software is freely distributable als long as this copyright part is also provided
# pyais libary must be available:
# pip install pyais
# 
# AIS specs:
# https://www.navcen.uscg.gov/?pageName=AISMessages


# aprsColl collects data for aprs.fi over COLLECT_TIME seconds, key is mmsi, type and, if existing, partno of message
# mtColl collects data for Marinetraffic over COLLECT_TIME seconds, key is the same

# TODO:
# implement statistcs :start, received bytes, sent bytes. Show compression factor (rec vs. sent), sent bytes/second
# implement TCP, several clients on a TCP-Port
# process other than record types 1,2,3,4,5,9,18,19,24,27


import platform
import sys
import threading
import time
import json
import socket
import requests
import pyais
import serial

from aiscredentials import DEBUG, SEND_TO_APRS, PRINT_TO_CONSOLE, COLLECT_TIME, NMEA_FILTER, INPUT_PROTO, INPUT_IP, INPUT_PORT, APRS_IP, APRS_CLIENT,\
  OUT_LIST
 
#just to make shure, that no obsolete data are sent
if INPUT_PROTO == 'FIL': 
  OUT_LIST = None
  SEND_TO_APRS = False  
readBuffer = ''
fail = ''
failCount = 0

if 'Windows' in platform.platform():
  OS = 'WIN'
  import logging as logger #not tested TODO
  LOG_ERR = "Error"
  LOG_INFO = "Info"
else:
  OS = 'UX'
  import syslog as logger
  LOG_ERR = logger.LOG_ERR
  LOG_INFO = logger.LOG_INFO

def logmsg(dst, msg):
  if DEBUG == 0:
    if OS == 'UX':
      logger.syslog(dst, '%s' % msg)
      if PRINT_TO_CONSOLE:
        print (msg)
    else:
      print ('Logprint', msg)
  else:
    print ('Logprint', msg)
def logerr(msg):
  logmsg(LOG_ERR, msg)
def loginf(msg):
  logmsg(LOG_INFO, msg)

def abort(msg): # bort program
  loginf ('Program stopped ' + msg)
  #TODO: close sockets, if any
  sys.exit()

class aiscollector():
  def __init__(self):
    loginf ('Starting aiscollector')
    self.inputPort = None
    self.aprsPort = None
    self.recBuffer = []
    self.outPorts = {}
    self.outAll = {}
    for name in OUT_LIST.keys():
      tmp0 = OUT_LIST[name]
      if tmp0['ACTIVE']:
        tmp1 = {'name':name,
                'proto': tmp0['PROTO'],
                'addr': (tmp0['IP'], tmp0['PORT']),
                'every': tmp0['EVERY']
               }
        tmp1.update({'socket': self.openNetOut(tmp1)})
        if tmp0['EVERY']:
          self.outAll.update({name: tmp1})
        else:
          self.outPorts.update({name: tmp1})
    #print (self.outPorts, '\r\n', self.outAll)   #DEBUG    
    
  #open input port 
    fail = ''  
    if INPUT_PROTO == 'SER':
      try:
        self.inputPort = serial.Serial(port = INPUT_IP,
                           baudrate = 38400,
                           bytesize = serial.EIGHTBITS,
                           timeout = 10)
      except Exception as e:
        fail = 'Error Open Serial ' + INPUT_IP + ': ' + str(e)

    elif INPUT_PROTO in ('TCP', 'UDP'):
      self.addr = (INPUT_IP, INPUT_PORT)
      fail = self.openNetIn(1)
    elif INPUT_PROTO == 'FIL': #ONLY for testing purpose, NEVER send to internet portals
      try:
        self.inputPort = open(INPUT_IP, 'r')
        #print ("Source:",INPUT_IP) #DEBUG
      except Exception as e:
        fail = 'Error open File ' + INPUT_IP + ': ' + str(e)
    else:
      fail = 'Wrong input protocol: ' + INPUT_PROTO
    if len(fail) > 0:
      abort(fail)
        
    if SEND_TO_APRS == True:
      self.aprsPort = APRS_IP

  #returns CRC-checked AIS Message with leading '!' or EOF or Null-String
  def readData(self):
    if len(self.recBuffer) == 0:
      received = ''
      try:
        if INPUT_PROTO == 'SER':
          received = self.inputPort.readline()
        elif INPUT_PROTO == 'TCP':
          received = self.inputPort.recv(1024)
        elif INPUT_PROTO == 'UDP':
          received, a = self.inputPort.recvfrom(1024)
        else: #file input
          received = self.inputPort.readline()
          if len(received) == 0:
            return 'EOF' #occurres only when reading file
          time.sleep (0.5)
      except Exception as e:
        logerr("Error reading data: " + str(e))

      if len(received) == 0:
        if INPUT_PROTO in ('TCP', 'UDP'):
          fail = self.openNetIn(1)
          if len(fail) > 0:
            abort (fail)
      if len(received) > 0:
        received = received.decode()      
        self.recBuffer = received.split('\r\n')
    if len(self.recBuffer) == 0:
      received = ''
    else:
      received = self.recBuffer.pop(0)
      if len(self.recBuffer) > 0 and self.recBuffer[0] == '':
        self.recBuffer.pop()
    #print ("Raw received:", len(self.recBuffer), received) #DEBUG
    if  type(received) is bytes: 
      received = received.decode()

    if len(received) < 15 or received[0:6] not in NMEA_FILTER: 
      return '' #not what I want

    #test integrity check #DEBUG
    #received = received[:12] + "*" + received[13:] #simulate error condition
    
    try:
      data, chksum = received[1:].split('*')
      calc_chksum = self.calcCheckSum(data)
      if int(chksum,16) != calc_chksum:
        raise ValueError("CRC")
    except Exception as e:
      logerr("Data Error :" + str(e) + " " +received)
      received = ''
    return received

  def calcCheckSum(self, data):
    calc_chksum = 0
    for c in data:
      calc_chksum ^= ord(c)
    return calc_chksum

  def aisDecode(self, data):
    try:
      msg = pyais.decode_msg(data)
    except Exception as e:
      msg = {'Error ': str(e)}
    return msg
  
  def openNetIn(self, maxFailCount):
    failCount = 0
    while failCount < maxFailCount:
      fail = ''
      try: 
        if self.inputPort != None:
          self.inputPort.close()
          del self.inputPort
        if INPUT_PROTO == 'TCP':
          self.inputPort = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          self.inputPort.connect(self.addr)
          break
        else:
          self.inputPort = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
          self.inputPort.bind(self.addr)
          break
      except Exception as e:
        failCount += 1
        fail = 'Error ' + str(failCount) + ' open ' + INPUT_PROTO + '-Port: ' + INPUT_IP + ':' + str(INPUT_PORT) + ': ' + str(e)
        logerr (fail)
        time.sleep(3)
        
    return fail
    
  def openNetOut(self, outParams):
    outSocket = None
    if outParams['proto'] == 'UDP':
      outSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    elif outParams['proto'] == 'TCP':
      outSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    else:
      abort('Aborting, output protocol ' + self.proto + ' not allowed, only TCP and UDP')
  
    outSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    outSocket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    
    if outParams['proto'] == 'TCP':
      try:
        outSocket.connect(outParams['addr'])
      except Exception as e:
        logerr('Error open ' + outParams['name'] + ' ' + outParams['proto'] + ' ' + str(outParams['addr']) + " " + str(e))
        outSocket = None
        
    return outSocket
    
#create a thread to send data to a specified destination
#it is assumed, that this takes much less time tha a new collection
#check for TIMEOUT (thread must not be active, wen new starts
class sender (threading.Thread):
  def __init__(self, socket, data):
    threading.Thread.__init__(self)
    self.threadName = socket['name']
    self.destSocket = socket['socket']
    self.addr = socket['addr']
    self.proto = socket['proto']
    self.data = data

  def run(self):
    if self.threadName != 'aprs.fi':
      if PRINT_TO_CONSOLE:
        print ("Want to send", str(len(self.data)), "packets in Thread", self.threadName, self.data)
      for i in self.data:
          if self.proto == 'TCP':
            try:
              if self.destSocket == None:
                #Try to establish a connection
                self.destSocket = reader.openNetOut(socket)
              if self.destSocket != None:
                self.destSocket.send((self.data[i] + '\r\n').encode())
            except Exception as e:
              logerr('ERROR sending TCP data to ' + str(self.destSocket) + ' ' + str(e))
              socket['socket'] = None
          else:
            try:
              #print('Sending UDP data to ' + self.threadName + " " + str(self.destSocket) + ' ' + str(self.port['addr'])) #DEBUG
              self.destSocket.sendto((self.data[i] + '\r\n').encode(), self.addr) 
            except Exception as e:
              logerr('ERROR sending UDP data to ' + str(self.destSocket) + ' ' + str(e))
              
    elif self.threadName == 'aprs.fi':
      allmsgs = []
      for i in self.data:
        allmsgs.append(self.data[i])
      path = {
        "name": APRS_CLIENT,
        "url": self.destSocket
        }
      groups = {
       "path": [path],
       "msgs": allmsgs
       }    #self.data[i]] }
      output = {
        "encodetime": time.strftime("%Y%m%d%H%M%S", time.gmtime()),
        "protocol": 'jsonais',
        "groups":  [groups] }
      try:
        post = json.dumps(output)
        r = requests.post(self.destSocket, files={'jsonais': (None, post)})
        #TODO: check for proper response r
        if DEBUG > 0:
          #print ('aprs.fi data:\r\n', post) #DEBUG
          #print ("aprs.fi reply: ",r) #DEBUG
          pass
      except Exception as e:
        if e == None: e = ''
        logerr('ERROR sending Data to ' + self.threadName + ': ' + str(e))
    time.sleep(.5) #DEBUG
    
def main():
  #collect msg in an array with mmsi and type as key, overwite existing
  #flush this array every n seconds to Marinetraffic and start new array
  reader = aiscollector()
  if reader.inputPort == None:
    logerr("aiscollector ABORT, cannot open port " + str(INPUT_PORT))
    sys.exit()
  z = 0
  outErrors = []
  aprsColl = mtColl = {}

  #collect for aprs.fi, all fields, used fields vary with 'type' and 'partno', real content depends on 'type'
  aprsTemplate = {}
  mtTemplate = {}
  aprsColl = {}
  mtColl = {}
  timeout = time.time() + COLLECT_TIME
  rawAis = ''
  localAddr = None
  
  #from here get messages for ever
  while True:
    while time.time() < timeout:
      rawAis = reader.readData()
      #print ("Raw Ais:", rawAis) #DEBUG
      if rawAis == 'EOF':
        abort ('EOF reached')
      if rawAis != b'': #else do nothing
        if len(reader.outAll) > 0:
          for outPartner in reader.outAll.keys():
            outSender = sender(reader.outAll.get(outPartner), {'0': rawAis})
            outSender.start()
     
      msg = reader.aisDecode(rawAis)
      #print ("MSG", msg) #DEBUG
      if 'type' in msg:
        if msg['type'] in (1,2,3,4,5,9,18,19,24,27):
          #common data for all types
          z += 1
          aprsKey = str(msg['mmsi']) + str(msg['type'])
          if msg['type'] == 24:
            aprsKey += str(msg['partno'])
          aprsRecord = aprsColl.get(aprsKey)
          if aprsRecord == None:
            aprsRecord = {}

          aprsRecord['mmsi'] = int(msg['mmsi'])
          aprsRecord['msgtype'] = msg['type']
          aprsRecord['rxtime'] =  time.strftime("%Y%m%d%H%M%S", time.gmtime())

          if msg['type'] in (1,2,3):
            aprsRecord['status'] = msg['status'].value
            aprsRecord['speed'] = msg['speed']
            aprsRecord['lat'] = msg['lat']
            aprsRecord['lon'] = msg['lon']
            aprsRecord['course'] = msg['course']
            aprsRecord['heading'] = msg['heading']
            #aprsRecord['maneuver'] = msg['maneuver'].value
            #aprsRecord['rot'] = msg['turn']

          if msg['type'] == 5:
            aprsRecord['imo'] = msg['imo']
            aprsRecord['callsign'] = msg['callsign']
            aprsRecord['shipname'] = msg['shipname'].replace('@',' ')
            aprsRecord['shiptype'] = msg['shiptype'].value
            aprsRecord['length'] = msg['to_bow'] + msg['to_stern']
            aprsRecord['width'] = msg['to_port'] + msg['to_starboard']
            aprsRecord['ref_front'] = msg['to_bow']
            aprsRecord['ref_left'] = msg['to_port']
            aprsRecord['eta'] = str(msg['month']).zfill(2) + str(msg['day']).zfill(2) + str(msg['hour']).zfill(2) + str(msg['minute']).zfill(2)
            aprsRecord['destination'] = msg['destination']
            aprsRecord['draught'] = msg['draught']

          if msg['type'] == 18:
            aprsRecord['lat'] = msg['lat']
            aprsRecord['lon'] = msg['lon']
            aprsRecord['cog'] = msg['course']
            aprsRecord['sog'] = msg['speed']
            aprsRecord['heading'] = msg['heading']

          if msg['type'] == 19:
            aprsRecord['lat'] = msg['lat']
            aprsRecord['lon'] = msg['lon']
            aprsRecord['course'] = msg['course']
            aprsRecord['sog'] = msg['speed']
            aprsRecord['heading'] = msg['heading']
            aprsRecord['shipname'] = msg['shipname'].replace('@',' ')
            aprsRecord['shiptype'] = msg['shiptype'].value
            aprsRecord['length'] = msg['to_bow'] + msg['to_stern']
            aprsRecord['width'] = msg['to_port'] + msg['to_starboard']
            aprsRecord['ref_front'] = msg['to_bow']
            aprsRecord['ref_left'] = msg['to_port']

          if msg['type'] == 24:
            aprsRecord['partno'] = msg['partno']
            if msg['partno'] == 0:
              aprsRecord['shipname'] = msg['shipname'].replace('@', ' ')
            if msg['partno'] == 1:
              aprsRecord['shiptype'] = msg['shiptype'].value
              aprsRecord['callsign'] = msg['callsign']
              aprsRecord['length'] = msg['to_bow'] + msg['to_stern']
              aprsRecord['width'] = msg['to_port'] + msg['to_starboard']
              aprsRecord['ref_front'] = msg['to_bow']
              aprsRecord['ref_left'] = msg['to_port']

          aprsColl.update({aprsKey:aprsRecord})

          mtKey = aprsKey
          mtColl.update({mtKey:rawAis}) #latest raw AIS packet for Marinetraffic

    if z > 0: #some data received in time theintervall
      #print ("Ready to Send", reader.outChannels, z, len(mtColl))
      if len(reader.outPorts) > 0:
        for outPartner in reader.outPorts.keys():
          outSender = sender(reader.outPorts.get(outPartner), mtColl.copy())
          outSender.start()
      if SEND_TO_APRS:
        apsender = sender({'name': 'aprs.fi', 'addr': APRS_CLIENT, 'socket': APRS_IP, 'proto': 'http'}, aprsColl.copy())
        apsender.start()

    #start new collection
    aprsColl.clear()
    mtColl.clear()
    timeout = time.time() + COLLECT_TIME
    z = 0
  #next time loop  

if __name__ == "__main__":
  main()
