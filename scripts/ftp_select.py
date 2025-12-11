# -*- coding: utf-8 -*-
"""
FTP File Selector - Choose any file from FTP and read it

Description:
- List all available files on FTP
- Select any file to read
- Show file content
- Parse hanger unload events
- Send signals to app.py

Use for:
- Testing with historical logs
- Choosing specific date
- Debugging
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


def get_file_list():
    """Get list of all files from FTP"""
    print("[FTP] Connecting to get file list...")
    
    try:
        ftp = FTP()
        ftp.connect(FTP_HOST, FTP_PORT, timeout=10)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_BASE_PATH)
        
        files = ftp.nlst()
        ftp.quit()
        
        # Sort files by date (newest first)
        files_sorted = sorted(files, reverse=True)
        return files_sorted
        
    except Exception as e:
        print(f"[ERROR] Failed to get file list: {e}")
        return []


def read_ftp_file(filename):
    """Read file from FTP"""
    print(f"[FTP] Reading file: {filename}")
    
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
        return False, None


def parse_hanger_exits(log_content):
    """Parse hanger unload events"""
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
                'event': 'unload'
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
    print("FTP FILE SELECTOR - Choose and Parse Any File")
    print("=" * 70)
    print()
    
    # Get file list
    print("Getting file list from FTP...")
    files = get_file_list()
    
    if not files:
        print("[ERROR] No files found on FTP")
        return
    
    print(f"[OK] Found {len(files)} files")
    print()
    
    # Show file list
    print("=" * 70)
    print("AVAILABLE FILES (newest first)")
    print("=" * 70)
    print()
    
    for i, filename in enumerate(files, 1):
        print(f"{i:2d}. {filename}")
    
    print()
    
    # Ask user to select file
    while True:
        try:
            choice = input("Enter file number (1-" + str(len(files)) + ") or 0 to exit: ")
            
            if choice == "0":
                print("Exiting...")
                return
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(files):
                selected_file = files[choice_num - 1]
                break
            else:
                print(f"Error: Enter number between 1 and {len(files)}")
        except ValueError:
            print("Error: Enter valid number")
    
    print()
    print(f"Selected: {selected_file}")
    print()
    
    # Read file
    success, content = read_ftp_file(selected_file)
    if not success or not content:
        print("[ERROR] Failed to read file")
        return
    
    print(f"[OK] File read successfully ({len(content)} bytes)")
    print()
    
    # Parse events
    print("Parsing hanger unload events...")
    exits = parse_hanger_exits(content)
    
    if not exits:
        print("[INFO] No hanger unload events found")
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
    
    # Ask to send signals
    send_choice = input("Send signals to app.py? (y/n): ").lower()
    
    if send_choice != 'y':
        print("Skipped sending signals")
        return
    
    print()
    print("=" * 70)
    print("SENDING SIGNALS TO APP")
    print("=" * 70)
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
    print(f"Total events: {len(exits)}")
    print(f"Signals sent: {sent_count}")
    print(f"Failed: {failed_count}")
    print()


if __name__ == "__main__":
    main()
