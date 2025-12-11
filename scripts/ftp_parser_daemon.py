# -*- coding: utf-8 -*-
"""
FTP Parser Daemon - Runs in background, checks for new logs every minute

Works with start.py controller
Reads only new lines (incremental mode)
Sends signals to app.py
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
import logging


# FTP Configuration
FTP_HOST = "172.17.11.194"
FTP_PORT = 21
FTP_USER = "omron"
FTP_PASS = "12345678"
FTP_BASE_PATH = "/MEMCARD1/messages/"

# App Configuration
APP_URL = "http://localhost:5000/api/signal"
APP_TIMEOUT = 5

# State file
STATE_FILE = "log_parser_state.json"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


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
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except:
        pass


def read_ftp_file_range(filename, start_byte=0):
    """Read file from FTP starting at specific byte position"""
    try:
        ftp = FTP()
        ftp.connect(FTP_HOST, FTP_PORT, timeout=10)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd(FTP_BASE_PATH)
        
        total_size = ftp.size(filename)
        
        if total_size < start_byte:
            logger.info(f"File reset: {start_byte} -> {total_size} bytes")
            start_byte = 0
        
        content_buffer = io.BytesIO()
        
        if start_byte > 0:
            ftp.sendcmd(f'REST {start_byte}')
        
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
            return True, text_content, total_size
        else:
            return False, None, total_size
            
    except Exception as e:
        logger.error(f"FTP error: {e}")
        return False, None, None


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
                'hanger': int(hanger)
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
        
        return response.status_code == 200
            
    except:
        return False


def main():
    logger.info("FTP Parser Daemon started")
    
    state = load_state()
    
    try:
        while True:
            # Get today's date
            today_date = datetime.now().strftime("%Y-%m-%d")
            filename = today_date
            
            # Check if date changed
            if state['file_date'] != today_date:
                logger.info(f"New day: {today_date}")
                state['byte_offset'] = 0
                state['file_date'] = today_date
            
            # Read new content
            success, content, total_size = read_ftp_file_range(filename, state['byte_offset'])
            
            if not success or content is None:
                logger.warning("Failed to read FTP file")
                time.sleep(60)
                continue
            
            if not content.strip():
                # No new content
                time.sleep(60)
                continue
            
            # Parse events
            exits = parse_hanger_exits(content)
            
            if exits:
                logger.info(f"Found {len(exits)} new hanger unloads")
                
                sent_count = 0
                for event in exits:
                    if send_signal_to_app(event['hanger'], event['time']):
                        sent_count += 1
                
                logger.info(f"Sent {sent_count}/{len(exits)} signals to app.py")
            
            # Update state
            state['byte_offset'] = total_size
            state['file_date'] = today_date
            save_state(state)
            
            # Wait 60 seconds
            time.sleep(60)
    
    except KeyboardInterrupt:
        logger.info("Daemon stopped")
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    main()
