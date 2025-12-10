# -*- coding: utf-8 -*-
"""
FTP Connection Test Script
Tests FTP connection and file reading with detailed diagnostics

Description:
- Checks FTP server availability
- Connects with credentials
- Shows file list in directory
- Performs 10 diagnostic checks

Use for:
- Testing FTP connection
- Network diagnostics
- Viewing available files
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


def log_step(step_num, status, message):
    """Log test step result"""
    icon = "[OK]" if status else "[FAIL]"
    print(f"Step {step_num:02d} {icon} {message}")
    return status


def test_ftp_connection():
    """Test FTP connection with 10 diagnostic steps"""
    print("=" * 60)
    print("FTP CONNECTION TEST")
    print(f"Host: {FTP_HOST}:{FTP_PORT}")
    print(f"User: {FTP_USER}")
    print(f"Path: {FTP_BASE_PATH}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    results = []
    ftp = None
    
    # Step 1: Check parameters
    step1 = bool(FTP_HOST and FTP_BASE_PATH)
    results.append(log_step(1, step1, f"Parameters check - Host: {FTP_HOST}"))
    
    # Step 2: Create FTP object
    try:
        ftp = FTP()
        results.append(log_step(2, True, "FTP object created"))
    except Exception as e:
        results.append(log_step(2, False, f"FTP object creation failed: {e}"))
        return False
    
    # Step 3: Connect to server
    try:
        ftp.connect(FTP_HOST, FTP_PORT, timeout=10)
        results.append(log_step(3, True, f"Connected to {FTP_HOST}:{FTP_PORT}"))
    except Exception as e:
        results.append(log_step(3, False, f"Connection failed: {e}"))
        return False
    
    # Step 4: Login
    try:
        ftp.login(FTP_USER, FTP_PASS)
        results.append(log_step(4, True, f"Logged in as {FTP_USER}"))
    except Exception as e:
        results.append(log_step(4, False, f"Login failed: {e}"))
        ftp.quit()
        return False
    
    # Step 5: Get server info
    try:
        welcome = ftp.getwelcome()
        results.append(log_step(5, True, f"Server response received"))
        print(f"       Message: {welcome[:50]}...")
    except Exception as e:
        results.append(log_step(5, False, f"Server info failed: {e}"))
    
    # Step 6: Navigate to directory
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
        print(f"       Files list:")
        for i, f in enumerate(files[:15]):
            print(f"         {i+1}. {f}")
        if len(files) > 15:
            print(f"         ... and {len(files) - 15} more files")
    except Exception as e:
        results.append(log_step(7, False, f"Directory listing failed: {e}"))
        files = []
    
    # Step 8: Check today's file
    today = datetime.now().strftime("%Y-%m-%d")
    today_exists = today in files
    results.append(log_step(8, today_exists, f"Today's file '{today}' {'FOUND' if today_exists else 'NOT FOUND'}"))
    
    # Step 9: Get today's file size
    if today_exists:
        try:
            size = ftp.size(today)
            results.append(log_step(9, True, f"Today's file size: {size} bytes"))
        except Exception as e:
            results.append(log_step(9, False, f"Could not get file size: {e}"))
    else:
        results.append(log_step(9, False, "Skipped - today's file not found"))
    
    # Step 10: Test read capability
    if today_exists:
        try:
            content_buffer = io.BytesIO()
            ftp.retrbinary(f"RETR {today}", content_buffer.write, blocksize=1024, rest=0)
            content_buffer.seek(0)
            first_bytes = content_buffer.read(100)
            results.append(log_step(10, True, f"File readable - first {len(first_bytes)} bytes OK"))
        except Exception as e:
            results.append(log_step(10, False, f"File read failed: {e}"))
    else:
        results.append(log_step(10, False, "Skipped - today's file not found"))
    
    # Cleanup
    try:
        ftp.quit()
    except:
        pass
    
    # Summary
    print()
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Status: {'SUCCESS' if passed == total else 'PARTIAL' if passed > 5 else 'FAILED'}")
    
    return passed == total


def main():
    print()
    print("FTP CONNECTION TEST")
    print()
    test_ftp_connection()
    print()


if __name__ == "__main__":
    main()
