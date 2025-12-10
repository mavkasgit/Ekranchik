# -*- coding: utf-8 -*-
"""
FTP File Reader Test Script
Tests FTP connection and file reading with detailed diagnostics
"""

import sys
import os
from ftplib import FTP
from datetime import datetime
import io


def log_step(step_num, status, message):
    """Log test step result"""
    icon = "[OK]" if status else "[FAIL]"
    print(f"Step {step_num:02d} {icon} {message}")
    return status


def test_ftp_connection(host, port, username, password, remote_path):
    """
    Test FTP connection and file reading with 10 diagnostic steps
    """
    print("=" * 60)
    print("FTP CONNECTION TEST")
    print(f"Host: {host}:{port}")
    print(f"Path: {remote_path}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    results = []
    ftp = None
    
    # Step 1: Check parameters
    step1 = bool(host and remote_path)
    results.append(log_step(1, step1, f"Parameters check - Host: {host}, Path: {remote_path}"))
    if not step1:
        print("ERROR: Host and path are required")
        return False
    
    # Step 2: Create FTP object
    try:
        ftp = FTP()
        results.append(log_step(2, True, "FTP object created"))
    except Exception as e:
        results.append(log_step(2, False, f"FTP object creation failed: {e}"))
        return False
    
    # Step 3: Connect to server
    try:
        ftp.connect(host, port, timeout=10)
        results.append(log_step(3, True, f"Connected to {host}:{port}"))
    except Exception as e:
        results.append(log_step(3, False, f"Connection failed: {e}"))
        return False
    
    # Step 4: Login
    try:
        if username:
            ftp.login(username, password)
            results.append(log_step(4, True, f"Logged in as {username}"))
        else:
            ftp.login()
            results.append(log_step(4, True, "Logged in as anonymous"))
    except Exception as e:
        results.append(log_step(4, False, f"Login failed: {e}"))
        ftp.quit()
        return False
    
    # Step 5: Get server info
    try:
        welcome = ftp.getwelcome()
        results.append(log_step(5, True, f"Server response: {welcome[:50]}..."))
    except Exception as e:
        results.append(log_step(5, False, f"Server info failed: {e}"))
    
    # Step 6: Navigate to directory
    dir_path = os.path.dirname(remote_path) if os.path.dirname(remote_path) else "/"
    file_name = os.path.basename(remote_path)
    
    try:
        if dir_path and dir_path != "/":
            ftp.cwd(dir_path)
        results.append(log_step(6, True, f"Changed to directory: {ftp.pwd()}"))
    except Exception as e:
        results.append(log_step(6, False, f"Directory change failed: {e}"))
        ftp.quit()
        return False
    
    # Step 7: List files in directory
    try:
        files = ftp.nlst()
        file_count = len(files)
        results.append(log_step(7, True, f"Found {file_count} files in directory"))
        print(f"       Files: {files[:10]}{'...' if len(files) > 10 else ''}")
    except Exception as e:
        results.append(log_step(7, False, f"Directory listing failed: {e}"))
        files = []
    
    # Step 8: Check if target file exists
    target_exists = file_name in files if files else False
    if not target_exists and files:
        # Try partial match
        matching = [f for f in files if file_name in f]
        if matching:
            file_name = matching[0]
            target_exists = True
            print(f"       Using matched file: {file_name}")
    
    results.append(log_step(8, target_exists, f"Target file '{file_name}' {'found' if target_exists else 'NOT found'}"))
    
    if not target_exists:
        print(f"       Available files: {files}")
        ftp.quit()
        return False
    
    # Step 9: Get file size
    try:
        size = ftp.size(file_name)
        results.append(log_step(9, True, f"File size: {size} bytes"))
    except Exception as e:
        results.append(log_step(9, False, f"Could not get file size: {e}"))
        size = "unknown"
    
    # Step 10: Read file content
    try:
        content_buffer = io.BytesIO()
        ftp.retrbinary(f"RETR {file_name}", content_buffer.write)
        content_buffer.seek(0)
        content = content_buffer.read()
        
        # Try different encodings
        text_content = None
        for encoding in ['utf-8', 'cp1251', 'cp866', 'latin-1']:
            try:
                text_content = content.decode(encoding)
                break
            except:
                continue
        
        if text_content:
            lines = text_content.split('\n')
            results.append(log_step(10, True, f"File read OK - {len(content)} bytes, {len(lines)} lines"))
            print()
            print("-" * 60)
            print("FILE CONTENT (first 20 lines):")
            print("-" * 60)
            for i, line in enumerate(lines[:20]):
                print(f"{i+1:03d}: {line.rstrip()}")
            if len(lines) > 20:
                print(f"... and {len(lines) - 20} more lines")
        else:
            results.append(log_step(10, False, "Could not decode file content"))
    except Exception as e:
        results.append(log_step(10, False, f"File read failed: {e}"))
    
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
    print("FTP FILE READER TEST")
    print("Usage: python ftp_test.py <ftp_host> <remote_path> [username] [password] [port]")
    print()
    
    if len(sys.argv) < 3:
        print("Example:")
        print("  python ftp_test.py 192.168.1.100 /data/log_2025-12-10.txt")
        print("  python ftp_test.py 192.168.1.100 /data/log_2025-12-10.txt user pass")
        print("  python ftp_test.py 192.168.1.100 /data/log_2025-12-10.txt user pass 21")
        print()
        
        # Interactive mode
        print("Enter parameters manually:")
        host = input("FTP Host (IP): ").strip()
        remote_path = input("Remote file path: ").strip()
        username = input("Username (empty for anonymous): ").strip()
        password = input("Password: ").strip() if username else ""
        port_str = input("Port (default 21): ").strip()
        port = int(port_str) if port_str else 21
    else:
        host = sys.argv[1]
        remote_path = sys.argv[2]
        username = sys.argv[3] if len(sys.argv) > 3 else ""
        password = sys.argv[4] if len(sys.argv) > 4 else ""
        port = int(sys.argv[5]) if len(sys.argv) > 5 else 21
    
    if host and remote_path:
        test_ftp_connection(host, port, username, password, remote_path)
    else:
        print("ERROR: Host and path are required")


if __name__ == "__main__":
    main()
