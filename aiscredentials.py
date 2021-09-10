# aiscredentials.py: Passwords etc. separated from Code
# dj8kl, 2021-09-10

DEBUG = 0
SEND_TO_MT = True
SEND_TO_APRS = True
SEND_TO_LOCAL = True
PRINT_TO_CONSOLE = False
COLLECT_TIME = 30 # Intervall vor collction of AIS messages per MMSI
                  # Seconds, Standard 60 or 120, Mininum 10
NMEA_FILTER = ['!AIVDM', '!AIVDO'] # only these NMEA records

INPUT_PROTO = 'SER' #'SER', 'TCP', 'UDP', 'FIL'
INPUT_IP = '/dev/ttyUais' #'serial port od filename or host name or ip
INPUT_PORT = 10110 # 

# aprs.fi
APRS_IP = 'https://aprs.fi/jsonais/post/<provided by aprs.fi>'
APRS_CLIENT = '<aprs name>' #ham radio call

# marinetraffic.com 5.9.207.224 use station dependent port
MT_PROTO = 'UDP'
MT_IP = '5.9.207.224'
MT_PORT = <MT port>

# local output for test purposes
LOCAL_PROTO = 'TCP'
LOCAL_IP = '192.168.58.24'
LOCAL_PORT = 10110

"""
Further info
Possible Content of records for aprs.fi
  {
  'mmsi':'',
  'msgtype':0,
  'partno':0,
  'lat': 0,
  'lon': 0,
  'speed':0,
  'course':0,
  'heading':0,
  'status':0,
  'shiptype':0,
  'callsign':'',
  'imo':'',
  'shipname':'',
  'draught':0,
  'ref_front':0, # 'to_bow':0 'to_stern':0,
  'to_left':0, # 'to_port':0, 'to_starboard':0
  'length':0,
  'width':0,
  'destination':'',
  'eta':'', # JJJMMTThhmmss
  'count':0,
  'rxtime':'' # reception utc
  }
"""
