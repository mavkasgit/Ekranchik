# -*- coding: utf-8 -*-
"""
FTP File Reader - Read today's log from FTP

Description:
- Automatically reads today's log file
- Shows file content (first lines)
- Performs 10 diagnostic checks

Use for:
- Viewing all events for the day
- Checking log content
- Diagnostics
"""

import sys
import os
from ftplib import FTP
from datetime import datetime
import io


# FTP Configuration
FTP_HOST = "172.17.11.194"
FTP_PORT = 21
FTP_USER = "omron"
FTP_PASS = "12345678"
FTP_BASE_PATH = "/MEMCARD1/messages/"


def get_today_filename():
    """Generate today's filename in format YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")


def log_step(step_num, status, message):
    """Log test step result"""
    icon = "[OK]" if status else "[FAIL]"
    print(f"Step {step_num:02d} {icon} {message}")
    return status


def read_ftp_file(filename):
    """Read file from FTP with 10 diagnostic steps"""
    print("=" * 70)
    print("FTP FILE READER")
    print(f"Host: {FTP_HOST}:{FTP_PORT}")
    print(f"User: {FTP_USER}")
    print(f"Base Path: {FTP_BASE_PATH}")
    print(f"Filename: {filename}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    
    results = []
    ftp = None
    
    # Step 1: Check filename parameter
    step1 = bool(filename)
    results.append(log_step(1, step1, f"Filename parameter check: {filename}"))
    if not step1:
        print("ERROR: Filename is required")
        return False
    
    # Step 2: Create FTP object
    try:
        ftp = FTP()
        results.append(log_step(2, True, "FTP object created successfully"))
    except Exception as e:
        results.append(log_step(2, False, f"FTP object creation failed: {e}"))
        return False
    
    # Step 3: Connect to FTP server
    try:
        ftp.connect(FTP_HOST, FTP_PORT, timeout=10)
        results.append(log_step(3, True, f"Connected to {FTP_HOST}:{FTP_PORT}"))
    except Exception as e:
        results.append(log_step(3, False, f"Connection failed: {e}"))
        return False
    
    # Step 4: Login to FTP server
    try:
        ftp.login(FTP_USER, FTP_PASS)
        results.append(log_step(4, True, f"Logged in as {FTP_USER}"))
    except Exception as e:
        results.append(log_step(4, False, f"Login failed: {e}"))
        ftp.quit()
        return False
    
    # Step 5: Get server welcome message
    try:
        welcome = ftp.getwelcome()
        results.append(log_step(5, True, f"Server response received"))
    except Exception as e:
        results.append(log_step(5, False, f"Server info failed: {e}"))
    
    # Step 6: Navigate to base directory
    try:
        ftp.cwd(FTP_BASE_PATH)
        current_dir = ftp.pwd()
        results.append(log_step(6, True, f"Changed to directory: {current_dir}"))
    except Exception as e:
        results.append(log_step(6, False, f"Directory change failed: {e}"))
        ftp.quit()
        return False
    
    # Step 7: List files in directory
    try:
        files = ftp.nlst()
        file_count = len(files)
        results.append(log_step(7, True, f"Found {file_count} files in directory"))
    except Exception as e:
        results.append(log_step(7, False, f"Directory listing failed: {e}"))
        files = []
        ftp.quit()
        return False
    
    # Step 8: Check if target file exists
    target_exists = filename in files
    results.append(log_step(8, target_exists, f"Target file '{filename}' {'FOUND' if target_exists else 'NOT FOUND'}"))
    
    if not target_exists:
        print(f"       Available files: {files[:10]}...")
        ftp.quit()
        return False
    
    # Step 9: Get file size
    try:
        size = ftp.size(filename)
        results.append(log_step(9, True, f"File size: {size} bytes"))
    except Exception as e:
        results.append(log_step(9, False, f"Could not get file size: {e}"))
    
    # Step 10: Read file content
    try:
        content_buffer = io.BytesIO()
        ftp.retrbinary(f"RETR {filename}", content_buffer.write)
        content_buffer.seek(0)
        content = content_buffer.read()
        
        # Try different encodings
        text_content = None
        used_encoding = None
        for encoding in ['utf-8', 'cp1251', 'cp866', 'latin-1', 'ascii']:
            try:
                text_content = content.decode(encoding)
                used_encoding = encoding
                break
            except:
                continue
        
        if text_content:
            lines = text_content.split('\n')
            results.append(log_step(10, True, f"File read OK - {len(content)} bytes, {len(lines)} lines"))
        else:
            results.append(log_step(10, False, "Could not decode file content"))
            ftp.quit()
            return False
            
    except Exception as e:
        results.append(log_step(10, False, f"File read failed: {e}"))
        ftp.quit()
        return False
    
    # Cleanup
    try:
        ftp.quit()
    except:
        pass
    
    # Display file content
    print()
    print("=" * 70)
    print(f"FILE CONTENT: {filename} (first 30 lines)")
    print("=" * 70)
    print()
    
    for i, line in enumerate(lines[:30]):
        if line.strip():
            print(f"{i+1:04d}: {line.rstrip()}")
    
    if len(lines) > 30:
        print(f"... and {len(lines) - 30} more lines")
    
    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Total lines: {len(lines)}")
    print("=" * 70)
    
    return passed == total


def main():
    today_date = get_today_filename()
    filename = today_date
    
    print()
    print("FTP FILE READER - TODAY'S FILE")
    print(f"Today's date: {today_date}")
    print()
    
    read_ftp_file(filename)


if __name__ == "__main__":
    main()
