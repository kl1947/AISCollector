# aiscredentials.py: Passwords etc. separated from Code
# dj8kl, 2021-09-16

DEBUG = 0
PRINT_TO_CONSOLE = False
SEND_TO_APRS = True
SEND_TO_LOCAL = False
COLLECT_TIME = 60 # Intervall vor collction of AIS messages per MMSI
                  # Seconds, Standard 60 or 120, Mininum 10
NMEA_FILTER = ['!AIVDM', '!AIVDO'] # only these NMEA records

INPUT_PROTO = 'SER' #'/root/tmp/nmea2.txt'  #'SER', 'TCP', 'UDP', 'FIL'
INPUT_IP = '/dev/ttyUais' #'Z:/home/pi/aisRecords.txt' #'rpi3weewx' # or Serial Port or Filename
                       # '/dev/ttyUais', '/dev/serial0', '~/aistestdata.txt', 192.168.58.24, 'rpi3weewx' 
INPUT_PORT = 10110 # 

# aprs.fi
APRS_IP = 'https://aprs.fi/jsonais/post/McHsZQ3PuJ'
APRS_CLIENT = 'dj8kl'

# marinetraffic.com: 5.9.207.224 
# fleetmon.com: 148.251.96.197 
OUT_LIST = {
  'Marinetraffic': {'ACTIVE': True, 'PROTO': 'TCP', 'IP': '5.9.207.224', 'PORT': <port>},
  'Fleetmon': {'ACTIVE': True, 'PROTO': 'TCP', 'IP': '148.251.96.197', 'PORT': <port>},
  }
  
# local output for test purposes TODO: allow more than one listener
LOCAL_PROTO = 'TCP'
LOCAL_IP = '192.168.58.24'
LOCAL_PORT = 10110
