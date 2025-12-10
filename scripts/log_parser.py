# -*- coding: utf-8 -*-
"""
Log Parser - Parse full log and send signals to app.py

Description:
- Reads entire log for today from FTP
- Finds all hanger unload events
- Sends signals to app.py
- Shows status for each event

What it looks for:
- Pattern: "Komanda ot CJ2M: Razgruzka podvesa - X v poz. 34"
- This is the moment when hanger exits the line

Use for:
- Initial log processing
- Syncing app.py with logs
- Sending all events for the day

Warning: reads entire file, may be slow for large files
"""

import sys
import os
from ftplib import FTP
from datetime import datetime
import io
import re
import requests
import time


# FTP Configuration
FTP_HOST = "172.17.11.194"
FTP_PORT = 21
FTP_USER = "omron"
FTP_PASS = "12345678"
FTP_BASE_PATH = "/MEMCARD1/messages/"

# App Configuration
APP_URL = "http://localhost:5000/api/signal"
APP_TIMEOUT = 5


def read_ftp_file(filename):
    """Read file from FTP"""
    print(f"[FTP] Reading file: {filename}")
    
    ftp = None
    try:
        ftp = FTP()
        ftp.connect(FTP_HOST, FTP_PORT, timeout=10)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_BASE_PATH)
        
        content_buffer = io.BytesIO()
        ftp.retrbinary(f"RETR {filename}", content_buffer.write)
        content_buffer.seek(0)
        content = content_buffer.read()
        
        text_content = None
        for encoding in ['utf-8', 'cp1251', 'cp866', 'latin-1', 'ascii']:
            try:
                text_content = content.decode(encoding)
                print(f"[OK] File decoded with {encoding}")
                break
            except:
                continue
        
        ftp.quit()
        
        if text_content:
            return True, text_content
        else:
            print("[FAIL] Could not decode file")
            return False, None
            
    except Exception as e:
        print(f"[FAIL] FTP error: {e}")
        if ftp:
            try:
                ftp.quit()
            except:
                pass
        return False, None


def parse_hanger_exits(log_content):
    """
    Parse log content and extract hanger FINAL UNLOAD times
    
    Looking for pattern:
    "HH:MM:SS.mmm L# Komanda ot CJ2M: Razgruzka podvesa - X v poz. 34."
    
    This is the moment when hanger exits the line (position 34 = exit point)
    """
    exits = []
    
    # Pattern for final unload from line
    pattern = r'(\d{2}):(\d{2}):(\d{2})\.\d+\s+L#\s+Команда\s+от\s+CJ2M:\s+Разгрузка\s+подвеса\s+-\s+(\d+)\s+в\s+поз\.\s+34'
    
    lines = log_content.split('\n')
    
    for line in lines:
        match = re.search(pattern, line)
        if match:
            h, m, s, hanger = match.groups()
            time_str = f"{h}:{m}:{s}"
            exits.append({
                'time': time_str,
                'hanger': int(hanger),
                'event': 'unload',
                'line': line.strip()
            })
    
    return exits


def send_signal_to_app(hanger_number, exit_time):
    """Send signal to app.py /api/signal endpoint"""
    try:
        payload = {
            'hanger_number': hanger_number,
            'exit_time': exit_time
        }
        
        response = requests.post(
            APP_URL,
            json=payload,
            timeout=APP_TIMEOUT
        )
        
        if response.status_code == 200:
            return True, response.text
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
            
    except requests.exceptions.ConnectionError:
        return False, "Connection refused - is app.py running?"
    except requests.exceptions.Timeout:
        return False, "Request timeout"
    except Exception as e:
        return False, str(e)


def main():
    print()
    print("=" * 70)
    print("LOG PARSER - Full File Mode")
    print("=" * 70)
    print()
    print("Configuration:")
    print(f"  FTP Host: {FTP_HOST}:{FTP_PORT}")
    print(f"  FTP Path: {FTP_BASE_PATH}")
    print(f"  App URL: {APP_URL}")
    print()
    
    # Get today's date
    today_date = datetime.now().strftime("%Y-%m-%d")
    filename = today_date
    
    print(f"Reading file: {filename}")
    print()
    
    # Read file from FTP
    success, content = read_ftp_file(filename)
    if not success or not content:
        print("[ERROR] Failed to read file from FTP")
        return
    
    print(f"[OK] File read successfully ({len(content)} bytes)")
    print()
    
    # Parse hanger exits
    print("Parsing hanger unload events...")
    exits = parse_hanger_exits(content)
    
    if not exits:
        print("[WARN] No hanger unload events found in log")
        return
    
    print(f"[OK] Found {len(exits)} hanger unload events")
    print()
    
    # Sort by time
    exits_sorted = sorted(exits, key=lambda x: x['time'])
    
    # Display events
    print("=" * 70)
    print("HANGER UNLOAD EVENTS")
    print("=" * 70)
    print()
    
    for i, event in enumerate(exits_sorted, 1):
        print(f"{i:3d}. [{event['time']}] Hanger {event['hanger']:2d}")
    
    print()
    print("=" * 70)
    print("SENDING SIGNALS TO APP")
    print("=" * 70)
    print()
    
    print(f"Sending {len(exits_sorted)} signals...")
    print()
    
    sent_count = 0
    failed_count = 0
    
    for event in exits_sorted:
        hanger = event['hanger']
        time_str = event['time']
        
        success, response = send_signal_to_app(hanger, time_str)
        
        if success:
            print(f"[OK] Hanger {hanger:2d} @ {time_str}")
            sent_count += 1
        else:
            print(f"[FAIL] Hanger {hanger:2d} @ {time_str} - {response}")
            failed_count += 1
        
        time.sleep(0.1)
    
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total events found: {len(exits)}")
    print(f"Signals sent: {sent_count}")
    print(f"Failed: {failed_count}")
    print()


if __name__ == "__main__":
    main()
