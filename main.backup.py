#!/usr/bin/env python3
"""
Main Tag Processing System for RTLS
Handles receiving and processing tag data from simulator
"""

import socket
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from parser import TagDataParser, TagDataBuffer
import json

class TagState:
    """Represents the state of a single tag"""
    
    def __init__(self, tag_id: str):
        self.tag_id = tag_id
        self.last_cnt: Optional[int] = None
        self.last_timestamp: Optional[str] = None
        self.last_seen: Optional[datetime] = None
        self.total_updates = 0
        self.lock = threading.Lock()
    
    def update(self, cnt: int, timestamp: str, parsed_timestamp: datetime) -> bool:
        """
        Update tag state with new data
        
        Returns:
            True if state was updated (CNT changed)
        """
        with self.lock:
            old_cnt = self.last_cnt
            
            # Update state
            self.last_cnt = cnt
            self.last_timestamp = timestamp
            self.last_seen = parsed_timestamp
            self.total_updates += 1
            
            # Return True if CNT changed
            return old_cnt != cnt
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state as dictionary"""
        with self.lock:
            return {
                'tag_id': self.tag_id,
                'last_cnt': self.last_cnt,
                'last_timestamp': self.last_timestamp,
                'last_seen': self.last_seen.isoformat() if self.last_seen else None,
                'total_updates': self.total_updates
            }

class TagProcessor:
    """Main tag processing system"""
    
    def __init__(self, host='localhost', port=9999):
        """
        Initialize tag processor
        
        Args:
            host: Host to listen on
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.running = False
        self.server_socket = None
        
        # Tag state management
        self.tag_states: Dict[str, TagState] = {}
        self.states_lock = threading.Lock()
        
        # Parser and buffer
        self.parser = TagDataParser()
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Statistics
        self.stats = {
            'total_received': 0,
            'total_processed': 0,
            'total_errors': 0,
            'start_time': None
        }
        self.stats_lock = threading.Lock()
    
    def get_tag_state(self, tag_id: str) -> Optional[TagState]:
        """Get or create tag state"""
        with self.states_lock:
            if tag_id not in self.tag_states:
                self.tag_states[tag_id] = TagState(tag_id)
            return self.tag_states[tag_id]
    
    def process_tag_data(self, parsed_data: Dict[str, Any]):
        """
        Process a single parsed tag data entry
        
        Args:
            parsed_data: Parsed tag data from parser
        """
        try:
            tag_id = parsed_data['tag_id']
            cnt = parsed_data['cnt']
            timestamp = parsed_data['timestamp']
            parsed_timestamp = parsed_data['parsed_timestamp']
            
            # Get tag state
            tag_state = self.get_tag_state(tag_id)
            
            # Validate sequence if we have previous data
            if not self.parser.validate_tag_sequence(tag_id, cnt, tag_state.last_cnt):
                with self.stats_lock:
                    self.stats['total_errors'] += 1
            
            # Update tag state
            cnt_changed = tag_state.update(cnt, timestamp, parsed_timestamp)
            
            # Log CNT changes
            if cnt_changed:
                self.logger.info(f"Tag {tag_id}: CNT updated to {cnt} at {timestamp}")
            
            # Update statistics
            with self.stats_lock:
                self.stats['total_processed'] += 1
                
        except Exception as e:
            self.logger.error(f"Error processing tag data: {e}")
            with self.stats_lock:
                self.stats['total_errors'] += 1
    
    def handle_client(self, client_socket, address):
        """Handle individual client connection"""
        self.logger.info(f"Client connected from {address}")
        
        buffer = TagDataBuffer()
        
        try:
            while self.running:
                try:
                    # Receive data
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        break
                    
                    with self.stats_lock:
                        self.stats['total_received'] += 1
                    
                    # Add to buffer and get complete lines
                    lines = buffer.add_data(data)
                    
                    # Parse and process each line
                    parsed_data_list = buffer.parse_lines(lines)
                    for parsed_data in parsed_data_list:
                        self.process_tag_data(parsed_data)
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    self.logger.error(f"Error handling client {address}: {e}")
                    break
                    
        finally:
            client_socket.close()
            self.logger.info(f"Client {address} disconnected")
    
    def start_server(self):
        """Start the tag processing server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)  # For clean shutdown
            
            self.logger.info(f"Tag processor listening on {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    client_socket.settimeout(5.0)
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address),
                        name=f"Client-{address[0]}:{address[1]}"
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.logger.error(f"Server error: {e}")
                    break
                    
        except Exception as e:
            self.logger.error(f"Failed to start server: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
            self.logger.info("Server stopped")
    
    def start(self):
        """Start the tag processor"""
        self.logger.info("Starting Tag Processor...")
        
        self.running = True
        with self.stats_lock:
            self.stats['start_time'] = datetime.now()
        
        # Start server in separate thread
        server_thread = threading.Thread(target=self.start_server, name="ServerThread")
        server_thread.daemon = True
        server_thread.start()
        
        # Start statistics reporter
        stats_thread = threading.Thread(target=self._stats_reporter, name="StatsThread")
        stats_thread.daemon = True
        stats_thread.start()
        
        return server_thread
    
    def stop(self):
        """Stop the tag processor"""
        self.logger.info("Stopping Tag Processor...")
        self.running = False
    
    def _stats_reporter(self):
        """Periodic statistics reporting"""
        while self.running:
            time.sleep(30)  # Report every 30 seconds
            if not self.running:
                break
                
            self.print_statistics()
    
    def print_statistics(self):
        """Print current statistics"""
        with self.stats_lock:
            stats = self.stats.copy()
        
        with self.states_lock:
            active_tags = len(self.tag_states)
            tag_states = {tag_id: state.get_state() 
                         for tag_id, state in self.tag_states.items()}
        
        uptime = datetime.now() - stats['start_time'] if stats['start_time'] else None
        
        print("\n" + "="*60)
        print("TAG PROCESSOR STATISTICS")
        print("="*60)
        print(f"Uptime: {uptime}")
        print(f"Total Received: {stats['total_received']}")
        print(f"Total Processed: {stats['total_processed']}")
        print(f"Total Errors: {stats['total_errors']}")
        print(f"Active Tags: {active_tags}")
        
        if tag_states:
            print("\nTag States:")
            print("-" * 40)
            for tag_id, state in tag_states.items():
                print(f"  {tag_id}: CNT={state['last_cnt']}, "
                      f"Updates={state['total_updates']}, "
                      f"Last={state['last_seen']}")
        print("="*60)
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get all tag states"""
        with self.states_lock:
            return {tag_id: state.get_state() 
                   for tag_id, state in self.tag_states.items()}
    
    def get_tag_state_dict(self, tag_id: str) -> Optional[Dict[str, Any]]:
        """Get specific tag state"""
        with self.states_lock:
            if tag_id in self.tag_states:
                return self.tag_states[tag_id].get_state()
        return None

def main():
    """Main function"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    # Create and start processor
    processor = TagProcessor()
    
    try:
        server_thread = processor.start()
        
        logger.info("Tag Processor started. Press Ctrl+C to stop.")
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        processor.stop()
        
        # Wait for server thread
        if 'server_thread' in locals():
            server_thread.join(timeout=5)
        
        logger.info("Tag Processor stopped")

if __name__ == '__main__':
    main()