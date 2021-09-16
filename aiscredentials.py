#!/usr/bin/python
# aiscollector.py read ais messages, collect (compress) over some time, send to aprs.fi (json) and marinetraffic.com
# version 0.3
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

# TODO: process other than record types 1,2,3,4,5,9,18,19,24,27
#       allow more than one local listener (use threading)

import platform
import sys
import threading
import time
import datetime
import json
import socket
import requests
import pyais
import serial

from aiscredentials2 import DEBUG, SEND_TO_APRS, PRINT_TO_CONSOLE, COLLECT_TIME, NMEA_FILTER, INPUT_PROTO, INPUT_IP, INPUT_PORT, APRS_IP, APRS_CLIENT,\
  OUT_LIST, SEND_TO_LOCAL, LOCAL_PROTO, LOCAL_IP, LOCAL_PORT
 
# just to make shure, that no obsolete data are sent
if INPUT_PROTO == 'FIL': 
  OUT_LIST = None
  SEND_TO_APRS = False  
readBuffer = ''
fail = ''
failCount = 0

if 'Windows' in platform.platform():
  OS = 'WIN'
  import logging as logger # not tested TODO
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

def abort(msg): # abort program
  loginf ('Program stopped ' + msg)
  sys.exit()

class aiscollector():
  def __init__(self):
    loginf ('Starting aiscollector2')
    self.inputPort = None
    self.aprsPort = None
    self.localPort = None
    self.recBuffer = []
    self.send_to_local = SEND_TO_LOCAL

  # open input port 
    fail = ''  
    if INPUT_PROTO == 'SER':
      try:
        self.inputPort = serial.Serial(port = INPUT_IP,
                           baudrate = 38400,
                           bytesize = serial.EIGHTBITS,
                           timeout = 10)
      except Exception as e:
        fail = 'Error Open Serial ' + INPUT_IP + ': ' + str(e)

    elif INPUT_PROTO in ('TCP', 'UDP'): # UDP TODO
      fail = self.openNetIn(0)
    elif INPUT_PROTO == 'FIL': # ONLY for testing purpose, NEVER send to Marinetraffic or aprs.pi
      try:
        self.inputPort = open(INPUT_IP, 'r')
        #print ("Source:",INPUT_IP) # DEBUG
      except Exception as e:
        fail = 'Error open File ' + INPUT_IP + ': ' + str(e)
    if len(fail) > 0:
      abort(fail)
      
    # open Output Ports
    self.outChannels = {}
    for name in OUT_LIST.keys():
      outParams = OUT_LIST[name]
      if outParams['ACTIVE']:
        outPort = None
        try:
          if outParams['PROTO'] == 'UDP':
            outPort = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            outPort.bind((outParams['IP'], outParams['PORT']))
            outPort.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
          elif outParams['PROTO'] == 'TCP':
            outPort = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            outPort.connect((outParams['IP'], outParams['PORT']))
            outPort.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
          else:
            pass 
        except Exception as e:
          logerr('Error open ' + name + ' ' + outParams['PROTO'] + ': ' + outParams['IP'] + ':' + str(outParams['PORT']) + ": " + str(e))
      if outPort != None:
        self.outChannels.update({name: outPort})

    # local port for test or other applications
    if self.send_to_local == True:
      try:
        """ #must be moved to a thread
        if LOCAL_PROTO == 'UDP':
          self.localPort = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
          self.localPort.bind(("", LOCAL_PORT))
          #self.localPort.setblocking(0)
        """
        if LOCAL_PROTO == 'TCP':
          self.localPort = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          self.localPort.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
          self.localPort.setblocking(0)
          self.localPort.bind((LOCAL_IP, LOCAL_PORT))
          self.localPort.listen(1) # for more listeners must be separate thread?
        else:
          pass   
      except Exception as e:
        logerr('Error open local port ' + LOCAL_PROTO + ': ' + LOCAL_IP + ':' + str(LOCAL_PORT) + ": " + str(e))
        self.send_to_local = False          
        
    if SEND_TO_APRS == True:
      self.aprsPort = APRS_IP

  # returns CRC-checked AIS Message with leading '!' or EOF or Null-String
  def readData(self):
    if len(self.recBuffer) == 0:
      received = ''
      try:
        if INPUT_PROTO == 'SER':
          received = self.inputPort.readline()
        elif INPUT_PROTO in ('TCP', 'UDP'):
          received = self.inputPort.recv(1024)
        else: # file input
          received = self.inputPort.readline()
          if len(received) == 0:
            return 'EOF' #occurres only when reading file
          time.sleep (0.5)
      except Exception as e:
        logerr("Error reading data: " + str(e))

      if len(received) == 0:
        if INPUT_PROTO in ('TCP', 'UDP'):
          fail = self.openNetIn(0)
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
    # print ("Raw received:", len(self.recBuffer), received) #DEBUG
    if  type(received) is bytes: 
      received = received.decode()

    if len(received) < 15 or received[0:6] not in NMEA_FILTER: 
      return '' # not what I want

    #check integrity
    #received = received[:12] + "*" + received[13:] # simulate error conditionG400
    
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
  
  def openNetIn(self, failCount):
    while failCount < 100:
      fail = ''
      try: # UDP TODO
        if self.inputPort != None:
          self.inputPort.close()
          del self.inputPort
        if INPUT_PROTO == 'TCP':
          self.inputPort = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          self.inputPort.connect((INPUT_IP, INPUT_PORT))
          break
        elif INPUT_PROTO == 'UDP':
          self.inputPort = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
          self.inputPort.bind((INPUT_IP, INPUT_PORT))
          break
        else:
          fail = 'IP-Input must be TCP or UDP'
          break
      except Exception as e:
        failCount += 1
        fail = 'Error ' + str(failCount) + ' open ' + INPUT_PROTO + '-Port: ' + INPUT_IP + ':' + str(INPUT_PORT) + ': ' + str(e)
        logerr (fail)
        time.sleep(3)
        
    return fail

#create a thread to send data to a specified destination
# it is assumed, that this takes much less time tha a new collection
# check for TIMEOUT (thread must not be active, wen new starts
class sender (threading.Thread):
  def __init__(self, threadID, name, destination, data, z0, z1):
    threading.Thread.__init__(self)
    self.id = threadID
    self.name = name
    self.dest = destination
    self.data = data
    self.totalCount = z0
    self.compressedCount = z1

  def run(self):
    z = 0
    if self.name != 'aprs':
      for i in self.data:
        z += 1
        try:
          self.dest.send(self.data[i].encode('utf-8'))
          # print ("Sent data to", self.name, "z:", z, self.data[i]) #DEBUG
        except Exception as e:
          if e == None: e = ''
          logerr('ERROR sending data to ' + str(self.dest) + ' ' + str(e))

    elif self.name == 'aprs':
      allmsgs = []
      for i in self.data:
        allmsgs.append(self.data[i])
      path = {
        "name": APRS_CLIENT,
        "url": self.dest
        }
      groups = {
       "path": [path],
       "msgs": allmsgs
       }    #self.data[i]] }
      output = {
        "encodetime": datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        "protocol": 'jsonais',
        "groups":  [groups] }
      try:
        z += 1
        post = json.dumps(output)
        r = requests.post(self.dest, files={'jsonais': (None, post)})
        if DEBUG > 0:
          #print ('aprs.fi data:\r\n', post) #DEBUG
          #print ("aprs.fi reply: ",r) #DEBUG
          pass
      except Exception as e:
        if e == None: e = ''
        logerr("ERROR sending Data to aprs.fi: " + str(e))

if __name__ == "__main__":
  # collect msg in an array with mmsi and type as key, overwite existing
  # flush this array every n seconds to Marinetraffic and start new array
  reader = aiscollector()
  if reader.inputPort == None:
    logerr("aiscollector ABORT, cannot open port " + str(INPUT_PORT))
    sys.exit()
  z = 0
  aprsColl = mtColl = {}

  # collect for aprs.fi, all fields, used fields vary with 'type' and 'partno', real content depends on 'type'
  aprsTemplate = {}
  mtTemplate = {}
  aprsColl = {}
  mtColl = {}
  timeout = time.time() + COLLECT_TIME
  rawAis = ''
  localAddr = None
  
  # from here get messages for ever
  while True:
    while time.time() < timeout:
      rawAis = reader.readData()
      # print ("Raw Ais:", rawAis) #DEBUG
      if rawAis == 'EOF':
        abort ('EOF reached')
      if rawAis != b'': # else do nothing
       
        if reader.send_to_local:
          try:
            if LOCAL_PROTO == 'UDP': # TODO, plus threading for more listeners
              if localAddr == None:
                try:
                  data, localAddr = reader.localPort.recvfrom(256)
                  print ("local Port:", LOCAL_PROTO, LOCAL_IP, LOCAL_PORT, rawAis) #DEBUG
                except Exception as e:
                  print ("localAddr Error", e)
                  pass
                if localAddr != None:
                  reader.localPort.sendto((rawAis + '\r\n').encode(), localAddr)
            else: # TCP
              if localAddr == None:
                try:
                  currentLocalPort, localAddr = reader.localPort.accept()
                except:
                  pass
              if  localAddr != None:
                #print ('Sending: ' + LOCAL_PROTO + ' data to local port ' +  LOCAL_IP + ':' + str(LOCAL_PORT) + " (" + localAddr + "): " + str(e) + '\r\n' + rawAis) #DEBUG               
                currentLocalPort.send((rawAis + '\r\n').encode())
          except Exception as e:
            logerr('ERROR sending ' + LOCAL_PROTO + ' data to local port ' +  LOCAL_IP + ':' + str(LOCAL_PORT) + ": " + str(e))
            localAddr = None
            
        msg = reader.aisDecode(rawAis)
        #print ("MSG", msg) # DEBUG
        if 'type' in msg:
          if msg['type'] in (1,2,3,4,5,9,18,19,24,27):
            # common data for all types
            z += 1
            aprsKey = str(msg['mmsi']) + str(msg['type'])
            if msg['type'] == 24:
              aprsKey += str(msg['partno'])
            aprsRecord = aprsColl.get(aprsKey)
            if aprsRecord == None:
              aprsRecord = {}

            aprsRecord['mmsi'] = int(msg['mmsi'])
            aprsRecord['msgtype'] = msg['type']
            aprsRecord['rxtime'] =  datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")

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
            mtColl.update({mtKey:rawAis}) # latest raw AIS packet for Marinetraffic

    if z > 0: # data received in intervall
      # print ("Ready to Send", reader.outChannels, z, len(mtColl))
      outCount = 1
      if len(reader.outChannels) > 0:
        for outPartner in reader.outChannels.keys():
          outSender = sender(outCount, outPartner, reader.outChannels.get(outPartner), mtColl.copy(), z, len(mtColl))
          outSender.start()
          outCount += 1
          # delay to separate prints
          # while outSender.is_alive(): time.sleep(.1) #DEBUG: allow konsistent prints
  
      if SEND_TO_APRS:
        apsender = sender(outCount, 'aprs.fi', APRS_IP, aprsColl.copy(), z, len(mtColl))
        apsender.start()

    # start new collection
    aprsColl.clear()
    mtColl.clear()
    timeout = time.time() + COLLECT_TIME
    z = 0
  # next time loop  
