#!/usr/bin/env python3
"""
Tag Simulator for RTLS System
Generates mock tag data in format: TAG,<tag_id>,<cnt>,<timestamp>
"""

import time
import random
import threading
from datetime import datetime
import socket
import json

class TagSimulator:
    def __init__(self, output_method='socket', host='localhost', port=9999):
        """
        Initialize Tag Simulator
        
        Args:
            output_method: 'socket', 'stdout', or 'file'
            host: Host for socket connection
            port: Port for socket connection
        """
        self.output_method = output_method
        self.host = host
        self.port = port
        self.running = False
        
        # Tag configurations
        self.tags = {
            'fa451f0755d8': {'cnt': 100, 'interval': 1.0, 'description': 'Helmet Tag Worker A'},
            'ab123c4567ef': {'cnt': 200, 'interval': 1.5, 'description': 'Safety Vest Tag Worker B'},
            '12def890abcd': {'cnt': 150, 'interval': 2.0, 'description': 'Tool Tag Station 1'},
        }
        
        self.socket_client = None
        self.file_handle = None
        
    def _get_timestamp(self):
        """Generate timestamp in required format: YYYYMMDDHHMMSS.fff"""
        now = datetime.now()
        return now.strftime("%Y%m%d%H%M%S.%f")[:-3]  # Remove last 3 digits for milliseconds
    
    def _format_tag_data(self, tag_id, cnt, timestamp):
        """Format tag data according to specification"""
        return f"TAG,{tag_id},{cnt},{timestamp}"
    
    def _send_data(self, data):
        """Send data based on configured output method"""
        try:
            if self.output_method == 'stdout':
                print(data, flush=True)
                
            elif self.output_method == 'socket':
                if self.socket_client:
                    self.socket_client.send((data + '\n').encode('utf-8'))
                    
            elif self.output_method == 'file':
                if self.file_handle:
                    self.file_handle.write(data + '\n')
                    self.file_handle.flush()
                    
        except Exception as e:
            print(f"Error sending data: {e}")
    
    def _setup_output(self):
        """Setup output method"""
        try:
            if self.output_method == 'socket':
                self.socket_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket_client.connect((self.host, self.port))
                print(f"Connected to {self.host}:{self.port}")
                
            elif self.output_method == 'file':
                self.file_handle = open('tag_data.log', 'w')
                print("Writing to tag_data.log")
                
            elif self.output_method == 'stdout':
                print("Writing to stdout")
                
        except Exception as e:
            print(f"Error setting up output: {e}")
            return False
        return True
    
    def _cleanup_output(self):
        """Cleanup output resources"""
        try:
            if self.socket_client:
                self.socket_client.close()
            if self.file_handle:
                self.file_handle.close()
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    def _simulate_tag(self, tag_id, config):
        """Simulate individual tag data generation"""
        while self.running:
            try:
                # Increment counter
                config['cnt'] += 1
                
                # Add some randomness to make it more realistic
                if random.random() < 0.1:  # 10% chance to skip increment
                    config['cnt'] += random.randint(1, 3)
                
                # Generate timestamp
                timestamp = self._get_timestamp()
                
                # Format and send data
                tag_data = self._format_tag_data(tag_id, config['cnt'], timestamp)
                self._send_data(tag_data)
                
                # Wait for next transmission
                time.sleep(config['interval'] + random.uniform(-0.1, 0.1))  # Add jitter
                
            except Exception as e:
                print(f"Error simulating tag {tag_id}: {e}")
                break
    
    def start(self):
        """Start the tag simulator"""
        print("Starting Tag Simulator...")
        
        if not self._setup_output():
            print("Failed to setup output method")
            return
        
        self.running = True
        
        # Start a thread for each tag
        threads = []
        for tag_id, config in self.tags.items():
            thread = threading.Thread(
                target=self._simulate_tag, 
                args=(tag_id, config),
                name=f"TagSim-{tag_id[:8]}"
            )
            thread.daemon = True
            thread.start()
            threads.append(thread)
            print(f"Started simulation for tag {tag_id} (interval: {config['interval']}s)")
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down simulator...")
            self.running = False
            
        # Wait for threads to finish
        for thread in threads:
            thread.join(timeout=2)
            
        self._cleanup_output()
        print("Tag Simulator stopped")
    
    def stop(self):
        """Stop the simulator"""
        self.running = False

def main():
    """Main function with command line options"""
    import argparse
    
    parser = argparse.ArgumentParser(description='RTLS Tag Simulator')
    parser.add_argument('--method', choices=['socket', 'stdout', 'file'], 
                       default='socket', help='Output method')
    parser.add_argument('--host', default='localhost', help='Host for socket connection')
    parser.add_argument('--port', type=int, default=9999, help='Port for socket connection')
    
    args = parser.parse_args()
    
    # Create and start simulator
    simulator = TagSimulator(
        output_method=args.method,
        host=args.host,
        port=args.port
    )
    
    try:
        simulator.start()
    except Exception as e:
        print(f"Simulator error: {e}")

if __name__ == '__main__':
    main()