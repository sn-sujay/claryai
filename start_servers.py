#!/usr/bin/env python3
"""
Script to start both the main ClaryAI server and the batch server.

This script starts both servers in separate processes.
"""

import os
import sys
import subprocess
import time
import signal
import atexit

# Server processes
main_server_process = None
batch_server_process = None

def start_main_server():
    """Start the main ClaryAI server."""
    print("Starting main ClaryAI server...")
    
    # Start the main server
    main_server_process = subprocess.Popen(
        ["python", "src/main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for the server to start
    time.sleep(2)
    
    # Check if the server started successfully
    if main_server_process.poll() is not None:
        print("Error: Main server failed to start")
        stdout, stderr = main_server_process.communicate()
        print(f"Stdout: {stdout}")
        print(f"Stderr: {stderr}")
        return None
    
    print("Main server started successfully")
    return main_server_process

def start_batch_server():
    """Start the batch server."""
    print("Starting batch server...")
    
    # Start the batch server
    batch_server_process = subprocess.Popen(
        ["python", "batch_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for the server to start
    time.sleep(2)
    
    # Check if the server started successfully
    if batch_server_process.poll() is not None:
        print("Error: Batch server failed to start")
        stdout, stderr = batch_server_process.communicate()
        print(f"Stdout: {stdout}")
        print(f"Stderr: {stderr}")
        return None
    
    print("Batch server started successfully")
    return batch_server_process

def stop_servers():
    """Stop both servers."""
    print("Stopping servers...")
    
    # Stop the main server
    if main_server_process is not None:
        main_server_process.terminate()
        try:
            main_server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            main_server_process.kill()
        print("Main server stopped")
    
    # Stop the batch server
    if batch_server_process is not None:
        batch_server_process.terminate()
        try:
            batch_server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            batch_server_process.kill()
        print("Batch server stopped")

def signal_handler(sig, frame):
    """Handle signals to stop servers gracefully."""
    print(f"Received signal {sig}")
    stop_servers()
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Register exit handler
    atexit.register(stop_servers)
    
    # Start servers
    batch_server_process = start_batch_server()
    if batch_server_process is None:
        sys.exit(1)
    
    main_server_process = start_main_server()
    if main_server_process is None:
        sys.exit(1)
    
    print("Both servers are running")
    print("Main server: http://localhost:8000")
    print("Batch server: http://localhost:8086")
    print("Press Ctrl+C to stop servers")
    
    # Keep the script running
    try:
        while True:
            # Check if servers are still running
            if main_server_process.poll() is not None:
                print("Main server stopped unexpectedly")
                stdout, stderr = main_server_process.communicate()
                print(f"Stdout: {stdout}")
                print(f"Stderr: {stderr}")
                break
            
            if batch_server_process.poll() is not None:
                print("Batch server stopped unexpectedly")
                stdout, stderr = batch_server_process.communicate()
                print(f"Stdout: {stdout}")
                print(f"Stderr: {stderr}")
                break
            
            time.sleep(1)
    except KeyboardInterrupt:
        print("Keyboard interrupt received")
    finally:
        stop_servers()
