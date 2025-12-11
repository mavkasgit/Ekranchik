# -*- coding: utf-8 -*-
"""
Main Controller - Manage all services from one place

Controls:
- app.py (Web interface)
- bot.py (Telegram bot)
- FTP log parser (incremental mode)

All in one window with status monitoring
"""

import subprocess
import time
import os
import sys
import signal
from datetime import datetime


class ServiceManager:
    def __init__(self):
        self.processes = {}
        self.running = True
        
    def log(self, service, message):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{service:15s}] {message}")
    
    def start_service(self, name, command):
        """Start a service"""
        try:
            self.log(name, f"Starting... ({command})")
            
            if name == "FTP Parser":
                # FTP parser runs in loop
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
            else:
                # Web and bot run normally
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
            
            self.processes[name] = process
            self.log(name, "Started successfully")
            return True
            
        except Exception as e:
            self.log(name, f"Failed to start: {e}")
            return False
    
    def stop_service(self, name):
        """Stop a service"""
        if name not in self.processes:
            self.log(name, "Not running")
            return
        
        try:
            self.log(name, "Stopping...")
            process = self.processes[name]
            process.terminate()
            
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.log(name, "Force killing...")
                process.kill()
            
            del self.processes[name]
            self.log(name, "Stopped")
            
        except Exception as e:
            self.log(name, f"Error stopping: {e}")
    
    def check_services(self):
        """Check if services are still running"""
        dead_services = []
        
        for name, process in list(self.processes.items()):
            if process.poll() is not None:
                dead_services.append(name)
        
        for name in dead_services:
            self.log(name, "Crashed! Restarting...")
            del self.processes[name]
            self.restart_service(name)
    
    def restart_service(self, name):
        """Restart a service"""
        self.stop_service(name)
        time.sleep(1)
        
        if name == "Web App":
            self.start_service(name, "python app.py")
        elif name == "Telegram Bot":
            self.start_service(name, "python bot.py")
        elif name == "FTP Parser":
            self.start_service(name, "python scripts/ftp_parser_daemon.py")
    
    def show_status(self):
        """Show status of all services"""
        print()
        print("=" * 70)
        print("SERVICE STATUS")
        print("=" * 70)
        
        services = ["Web App", "Telegram Bot", "FTP Parser"]
        
        for service in services:
            if service in self.processes:
                process = self.processes[service]
                status = "RUNNING" if process.poll() is None else "STOPPED"
                print(f"  {service:20s} : {status}")
            else:
                print(f"  {service:20s} : STOPPED")
        
        print("=" * 70)
        print()
    
    def run(self):
        """Main loop"""
        print()
        print("=" * 70)
        print("SYSTEM CONTROLLER - All Services")
        print("=" * 70)
        print()
        print("Starting all services...")
        print()
        
        # Start all services
        self.start_service("Web App", "python app.py")
        time.sleep(2)
        
        self.start_service("Telegram Bot", "python bot.py")
        time.sleep(2)
        
        self.start_service("FTP Parser", "python scripts/ftp_parser_daemon.py")
        time.sleep(1)
        
        self.show_status()
        
        print("All services started!")
        print()
        print("Commands:")
        print("  s - Show status")
        print("  r - Restart all")
        print("  q - Quit")
        print()
        
        # Main loop
        try:
            while self.running:
                # Check services every 10 seconds
                self.check_services()
                
                # Show menu
                try:
                    cmd = input("Command (s/r/q): ").lower().strip()
                    
                    if cmd == "s":
                        self.show_status()
                    elif cmd == "r":
                        print()
                        print("Restarting all services...")
                        self.restart_service("Web App")
                        time.sleep(1)
                        self.restart_service("Telegram Bot")
                        time.sleep(1)
                        self.restart_service("FTP Parser")
                        self.show_status()
                    elif cmd == "q":
                        self.running = False
                    else:
                        print("Unknown command")
                
                except KeyboardInterrupt:
                    self.running = False
                
        except KeyboardInterrupt:
            self.running = False
        
        # Cleanup
        print()
        print("Stopping all services...")
        
        for service in list(self.processes.keys()):
            self.stop_service(service)
        
        print()
        print("All services stopped. Goodbye!")
        print()


def main():
    manager = ServiceManager()
    
    try:
        manager.run()
    except Exception as e:
        print(f"Error: {e}")
        
        # Cleanup on error
        for service in list(manager.processes.keys()):
            manager.stop_service(service)


if __name__ == "__main__":
    main()
