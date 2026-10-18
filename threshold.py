import pymysql
import time
import requests
from pymysql.cursors import DictCursor

conn = pymysql.connect(
    host="YOUR_DB_HOST",
    user="YOUR_DB_USER",
    password="YOUR_DB_PASS",
    database="YOUR_DB_NAME",
    cursorclass=DictCursor,   # rows come back as dicts
)

# sensorID = 1 = Inside Box
# sensorID = 2 = Inside Dome

API = "http://localhost:5000/api"   # your backend's PORT
FAN_ID = 1                          # <- from /api/actuators
MIST_ID = 2                         # <- from /api/actuators

# unit = vpd
FAN_ON_THRESHOLD = 0.2
FAN_OFF_THRESHOLD = 0.35
MIST_ON_THRESHOLD = 0.5
MIST_OFF_THRESHOLD = 0.35

FAN_DUTY = 100          # % when the fan is on

SQL = ("SELECT * FROM SensorLog WHERE sensorID = %s "
       "ORDER BY datetime DESC LIMIT 1")

def send(actuator_id, action, duty=None):
    """POST a command. Returns True only if the backend accepted it."""
    body = {"actuatorID": actuator_id, "action": action,
            "triggerSource": "AUTOMATION"}
    if duty is not None:
        body["pwmDutyPercent"] = duty
    try:
        r = requests.post(f"{API}/actuatorCommand", json=body, timeout=5)
        return r.status_code == 201
    except requests.RequestException as e:
        print("  command failed:", e)
        return False

fan_on = None    # None = unknown; we have not commanded it yet
mist_on = None

try:
    while True:
        # conn.ping(reconnect=True)   # reconnect if MySQL dropped the connection

        latest = {}
        with conn.cursor() as cur:
            for sid in (1, 2):
                cur.execute(SQL, (sid,))
                latest[sid] = cur.fetchone()   # None if no rows

        row1 = latest[1]
        datetime = row1["datetime"]
        sID1_temp = float(row1["temperature"])
        sID1_humi = float(row1["humidity"])
        sID1_vpd = float(row1["VPD"])
        row2 = latest[2]
        sID2_temp = float(row2["temperature"])
        sID2_humi = float(row2["humidity"])
        sID2_vpd = float(row2["VPD"])

        print("----------")
        print(datetime)
        print("sensorID = 1 , temp:", sID1_temp, ", humi:", sID1_humi, ", vpd:", sID1_vpd)
        print("sensorID = 2 , temp:", sID2_temp, ", humi:", sID2_humi, ", vpd:", sID2_vpd)
        print("")
        print("Fan:", fan_on, ", Mist:", mist_on)

        # fan on when vpd < 0.2 and humi of "inside box" is less than humi of "inside dome"
        if sID1_vpd < FAN_ON_THRESHOLD and fan_on is not True and sID1_humi < sID2_humi:
            if send(FAN_ID, "SET_SPEED", FAN_DUTY):
                fan_on = True
                print("set fan ON")
        # fan off when vpd >= 0.35
        elif sID1_vpd >= FAN_OFF_THRESHOLD and fan_on is not False:
            if send(FAN_ID, "OFF"):
                fan_on = False
                print("set fan OFF")

        # mist on when vpd > 0.5
        if sID1_vpd > MIST_ON_THRESHOLD and mist_on is not True:
            if send(MIST_ID, "ON"):
                mist_on = True
                print("set mist ON")
        # mist off when vpd <= 0.35
        elif sID1_vpd <= MIST_OFF_THRESHOLD and mist_on is not False:
            if send(MIST_ID, "OFF"):
                mist_on = False
                print("set mist OFF") 

        time.sleep(60)       # sleep (seconds)
except KeyboardInterrupt:
    print("Stopped")
finally:
    conn.close()