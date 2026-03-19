import csv
import random
from datetime import datetime, timedelta

def generate_telemetry_csv(filename="demosat_telemetry.csv"):
    # Schema keys from EhaItem.DICT_VALID_KEYS
    fieldnames = [
        'recordType', 'sessionId', 'sessionHost', 'channelId', 'dssId', 
        'vcid', 'name', 'module', 'ert', 'scet', 'rct', 'lst', 
        'sclk', 'dn', 'dnStr', 'eu', 'status', 'dnAlarmState', 
        'euAlarmState', 'realtime', 'type'
    ]

    # Configuration based on Channel.xml
    channels = [
        {"id": "EPS-0001", "name": "BATTERY_VOLTAGE", "mod": "eps", "vcid": 0},
        {"id": "EPS-0002", "name": "BUS_CURRENT", "mod": "eps", "vcid": 0},
        {"id": "INST-0003", "name": "CCD_TEMP", "mod": "inst", "vcid": 17},
        {"id": "ADCS-2001", "name": "TARGET_LAT_ERR", "mod": "adcs", "vcid": 0},
        {"id": "SYS-0002", "name": "BOOT_COUNT", "mod": "sys", "vcid": 0},
        {"id": "ADCS-1001", "name": "EST_Q1", "mod": "adcs", "vcid": 0},
        {"id": "ADCS-1002", "name": "EST_Q2", "mod": "adcs", "vcid": 0},
        {"id": "ADCS-1003", "name": "EST_Q3", "mod": "adcs", "vcid": 0},
        {"id": "ADCS-1004", "name": "EST_Q4", "mod": "adcs", "vcid": 0},
        {"id": "TEL-0003", "name": "VCDU_COUNTER", "mod": "tel", "vcid": 17},
    ]

    base_scet = datetime(2026, 1, 25, 12, 0, 0)
    base_sclk = 1737817192.0
    
    with open(filename, mode='w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for ch in channels:
            current_scet = base_scet
            current_sclk = base_sclk
            
            for i in range(50):
                # 1. Create irregular timing (1-5 seconds jitter)
                jitter = random.uniform(1.0, 5.0)
                current_scet += timedelta(seconds=jitter)
                current_sclk += jitter
                ert = current_scet + timedelta(seconds=10) # 10s light delay simulation

                # 2. Simulate Channel Logic & Alarm Violations
                dn, eu, alarm = 0, 0.0, None
                
                if ch['id'] == "EPS-0001": # Battery Voltage
                    # Start at 2200 DN (RED), drop to 1900 DN (NOMINAL)
                    dn = max(1900, 2200 - (i * 8))
                    eu = (0.00001 * (dn**2)) + (0.015 * dn) # Quadratic per XML
                    alarm = "RED" if eu > 32.5 else ("YELLOW" if eu > 31.8 else None)
                
                elif ch['id'] == "EPS-0002": # Bus Current
                    # Random spikes to simulate heaters
                    eu = random.uniform(1.0, 2.0)
                    if i in [10, 11, 30, 31]: eu += 3.0 # Spike
                    dn = round(eu)
                    alarm = "RED" if eu > 4.5 else ("YELLOW" if eu > 3.5 else None)
                
                elif ch['id'] == "INST-0003": # CCD Temp
                    # Linear slope: slope 0.12, intercept -50.0
                    dn = 500 + (i * 10) 
                    eu = (dn * 0.12) - 50.0
                    alarm = "RED" if eu > 45.0 else ("YELLOW" if eu > 35.0 else None)

                elif ch['id'] == "TEL-0003": # VCDU Counter
                    dn = 5000 + i
                    eu = float(dn)
                
                else: # Default for Quaternions/Boots
                    dn = round(random.uniform(0, 1)) if "EST_Q" in ch['name'] else 12
                    eu = float(dn)

                # 3. Write Row
                writer.writerow({
                    'recordType': 'EHA',
                    'sessionId': 903,
                    'sessionHost': 'GND-STN-01',
                    'channelId': ch['id'],
                    'dssId': 25,
                    'vcid': ch['vcid'],
                    'name': ch['name'],
                    'module': ch['mod'],
                    'ert': ert.strftime('%Y-%jT%H:%M:%S.%f')[:-3],
                    'scet': current_scet.strftime('%Y-%jT%H:%M:%S.%f')[:-3],
                    'rct': '',
                    'lst': '',
                    'sclk': current_sclk,
                    'dn': dn,
                    'dnStr': None,
                    'eu': round(eu, 4),
                    'status': None,
                    'dnAlarmState': None,
                    'euAlarmState': alarm,
                    'realtime': True,
                    'type': 'FSW'
                })

    print(f"Generated {filename} with 500 records.")

if __name__ == "__main__":
    generate_telemetry_csv()