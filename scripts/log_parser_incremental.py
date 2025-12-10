# -*- coding: utf-8 -*-
"""
Incremental Log Parser - Read only NEW lines from FTP log

Description:
- Reads only added lines (saves traffic)
- Saves position in file (log_parser_state.json)
- Ideal for frequent runs (every minute)

How it works:
1. Saves file position (byte offset)
2. On next run reads only from that position
3. Parses only new events
4. Sends signals to app.py
5. Updates position

Use for:
- Regular runs (every minute)
- Minimizing FTP traffic
- Continuous monitoring

Recommended: run every minute!
"""

import sys
import os
from ftplib import FTP
from datetime import datetime
import io
import re
import requests
import time
import json


# FTP Configuration
FTP_HOST = "172.17.11.194"
FTP_PORT = 21
FTP_USER = "omron"
FTP_PASS = "12345678"
FTP_BASE_PATH = "/MEMCARD1/messages/"

# App Configuration
APP_URL = "http://localhost:5000/api/signal"
APP_TIMEOUT = 5

# State file - saves position in file
STATE_FILE = "log_parser_state.json"


def load_state():
    """Load last file position and date"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {'file_date': None, 'file_size': 0, 'byte_offset': 0}


def save_state(state):
    """Save current file position and date"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def read_ftp_file_range(filename, start_byte=0):
    """
    Read file from FTP starting at specific byte position
    Returns: (success, content, total_size)
    """
    print(f"[FTP] Reading file: {filename} from byte {start_byte}")
    
    ftp = None
    try:
        ftp = FTP()
        ftp.connect(FTP_HOST, FTP_PORT, timeout=10)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_BASE_PATH)
        
        # Get total file size
        total_size = ftp.size(filename)
        
        # If file is smaller than our offset - file was reset
        if total_size < start_byte:
            print(f"[WARN] File was reset (was {start_byte} bytes, now {total_size})")
            start_byte = 0
        
        # Read from start_byte to end
        content_buffer = io.BytesIO()
        
        if start_byte > 0:
            # Use REST command to start from specific position
            ftp.sendcmd(f'REST {start_byte}')
        
        ftp.retrbinary(f"RETR {filename}", content_buffer.write)
        content_buffer.seek(0)
        content = content_buffer.read()
        
        # Try different encodings
        text_content = None
        for encoding in ['utf-8', 'cp1251', 'cp866', 'latin-1', 'ascii']:
            try:
                text_content = content.decode(encoding)
                break
            except:
                continue
        
        ftp.quit()
        
        if text_content:
            return True, text_content, total_size
        else:
            print("[FAIL] Could not decode file")
            return False, None, total_size
            
    except Exception as e:
        print(f"[FAIL] FTP error: {e}")
        if ftp:
            try:
                ftp.quit()
            except:
                pass
        return False, None, None


def parse_hanger_exits(log_content):
    """Parse only UNLOAD events from log content"""
    exits = []
    
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
    """Send signal to app.py"""
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
            return False, f"HTTP {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return False, "Connection refused"
    except Exception as e:
        return False, str(e)


def main():
    print()
    print("=" * 70)
    print("INCREMENTAL LOG PARSER - Read Only New Lines")
    print("=" * 70)
    print()
    
    # Load previous state
    state = load_state()
    print(f"[STATE] Last position: byte {state['byte_offset']}")
    print(f"[STATE] Last file date: {state['file_date']}")
    print()
    
    # Get today's date
    today_date = datetime.now().strftime("%Y-%m-%d")
    filename = today_date
    
    # Check if date changed (new day = new file)
    if state['file_date'] != today_date:
        print(f"[NEW DAY] Date changed from {state['file_date']} to {today_date}")
        state['byte_offset'] = 0
        state['file_date'] = today_date
    
    # Read only new content
    success, content, total_size = read_ftp_file_range(filename, state['byte_offset'])
    
    if not success or content is None:
        print("[ERROR] Failed to read file from FTP")
        return
    
    if not content.strip():
        print("[INFO] No new content")
        # Update state anyway
        if total_size:
            state['byte_offset'] = total_size
            save_state(state)
        return
    
    print(f"[OK] Read {len(content)} bytes (total file: {total_size} bytes)")
    print()
    
    # Parse new events
    exits = parse_hanger_exits(content)
    
    if not exits:
        print("[INFO] No new unload events found")
        # Update state anyway
        state['byte_offset'] = total_size
        save_state(state)
        return
    
    print(f"[OK] Found {len(exits)} new unload events")
    print()
    
    # Display events
    print("=" * 70)
    print("NEW HANGER UNLOADS")
    print("=" * 70)
    print()
    
    for i, event in enumerate(exits, 1):
        print(f"{i:3d}. [{event['time']}] Hanger {event['hanger']:2d}")
    
    print()
    print("=" * 70)
    print("SENDING SIGNALS TO APP")
    print("=" * 70)
    print()
    
    sent_count = 0
    failed_count = 0
    
    for event in exits:
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
    print(f"New events: {len(exits)}")
    print(f"Signals sent: {sent_count}")
    print(f"Failed: {failed_count}")
    print()
    
    # Update state
    state['byte_offset'] = total_size
    state['file_date'] = today_date
    save_state(state)
    
    print(f"[STATE] Saved position: byte {state['byte_offset']}")
    print()


if __name__ == "__main__":
    main()
