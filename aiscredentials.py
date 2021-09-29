# aiscredentials.py: Passwords etc. separated from Code
# dj8kl, 2021-09-23

DEBUG = 0
PRINT_TO_CONSOLE = False
SEND_TO_APRS = True

COLLECT_TIME = 60 # Intervall vor collction of AIS messages per MMSI
                  # Seconds, Standard 60 or 120, Mininum 10
NMEA_FILTER = ['!AIVDM', '!AIVDO'] # only these NMEA records

INPUT_PROTO = 'SER' #'/root/tmp/nmea2.txt'  #'SER', 'TCP', 'UDP', 'FIL'
INPUT_IP = '/dev/ttyUais' #'Z:/home/pi/aisRecords.txt' #'rpi3weewx' # or Serial Port or Filename
                       # '/dev/ttyUais', '/dev/serial0', '~/aistestdata.txt', 192.168.58.24, 'rpi3weewx' 
INPUT_PORT = 5006 # 

# aprs.fi
APRS_IP = 'https://aprs.fi/jsonais/post/<ID>'
APRS_CLIENT = 'nnnnn'

# marinetraffic.com: 5.9.207.224 Station ID/Port
#                    https://www.marinetraffic.com/en/ais/details/stations/<id>/
# fleetmon.com: 148.251.96.197 Station ID/Port
#               https://www.fleetmon.com/my/ais-stations/<id>
# EVERY: override collection of packets = send every
OUT_LIST = {
  'Marinetraffic': {'ACTIVE': True, 'PROTO': 'UDP', 'IP': '5.9.207.224', 'PORT': <PORT>, 'EVERY': False},
  'Fleetmon': {'ACTIVE': True, 'PROTO': 'UDP', 'IP': '148.251.96.197', 'PORT': <PORT>, 'EVERY': False},
  'Local': {'ACTIVE': True, 'PROTO': 'UDP', 'IP': '192.168.58.24', 'PORT': 5005, 'EVERY': True},
  }
