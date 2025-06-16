#!/usr/bin/env python3
"""
Tag Data Parser for RTLS System
Handles parsing and validation of tag data format: TAG,<tag_id>,<cnt>,<timestamp>
"""

import re
import logging
from datetime import datetime
from typing import Optional, Dict, Any

class TagDataParser:
    def __init__(self):
        """Initialize the tag data parser"""
        self.logger = logging.getLogger(__name__)
        
        # Regular expression for tag data validation
        self.tag_pattern = re.compile(
            r'^TAG,([a-fA-F0-9]+),(\d+),(\d{14}\.\d{3})$'
        )
        
    def parse_tag_data(self, data_line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single line of tag data
        
        Args:
            data_line: Raw data line to parse
            
        Returns:
            Dict with parsed data or None if invalid
            {
                'tag_id': str,
                'cnt': int,
                'timestamp': str,
                'parsed_timestamp': datetime
            }
        """
        try:
            # Remove whitespace
            data_line = data_line.strip()
            
            if not data_line:
                return None
                
            # Match against pattern
            match = self.tag_pattern.match(data_line)
            if not match:
                self.logger.warning(f"Invalid tag data format: {data_line}")
                return None
            
            tag_id, cnt_str, timestamp_str = match.groups()
            
            # Validate and convert data
            try:
                cnt = int(cnt_str)
                if cnt < 0:
                    self.logger.warning(f"Invalid counter value: {cnt}")
                    return None
            except ValueError:
                self.logger.warning(f"Invalid counter format: {cnt_str}")
                return None
            
            # Parse timestamp
            try:
                parsed_timestamp = self._parse_timestamp(timestamp_str)
            except ValueError as e:
                self.logger.warning(f"Invalid timestamp format: {timestamp_str} - {e}")
                return None
            
            # Validate tag_id format (hexadecimal)
            if not re.match(r'^[a-fA-F0-9]+$', tag_id):
                self.logger.warning(f"Invalid tag_id format: {tag_id}")
                return None
            
            return {
                'tag_id': tag_id.lower(),  # Normalize to lowercase
                'cnt': cnt,
                'timestamp': timestamp_str,
                'parsed_timestamp': parsed_timestamp,
                'raw_data': data_line
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing tag data '{data_line}': {e}")
            return None
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """
        Parse timestamp string to datetime object
        
        Args:
            timestamp_str: Timestamp in format YYYYMMDDHHMMSS.fff
            
        Returns:
            datetime object
        """
        try:
            # Format: 20240503140059.456
            return datetime.strptime(timestamp_str, "%Y%m%d%H%M%S.%f")
        except ValueError:
            raise ValueError(f"Timestamp must be in format YYYYMMDDHHMMSS.fff")
    
    def validate_tag_sequence(self, tag_id: str, new_cnt: int, last_cnt: Optional[int]) -> bool:
        """
        Validate that counter sequence is reasonable
        
        Args:
            tag_id: Tag identifier
            new_cnt: New counter value
            last_cnt: Last known counter value
            
        Returns:
            True if sequence is valid
        """
        if last_cnt is None:
            return True
        
        # Counter should generally increase
        if new_cnt <= last_cnt:
            self.logger.warning(f"Tag {tag_id}: Counter decreased or stayed same. "
                              f"Last: {last_cnt}, New: {new_cnt}")
            return False
        
        # Check for reasonable increment (not too large jump)
        increment = new_cnt - last_cnt
        if increment > 1000:  # Configurable threshold
            self.logger.warning(f"Tag {tag_id}: Large counter jump detected. "
                              f"Increment: {increment}")
            return False
        
        return True
    
    def is_valid_tag_format(self, data_line: str) -> bool:
        """
        Quick check if data line matches tag format
        
        Args:
            data_line: Data line to check
            
        Returns:
            True if format matches
        """
        return bool(self.tag_pattern.match(data_line.strip()))
    
    def extract_tag_id(self, data_line: str) -> Optional[str]:
        """
        Extract tag ID from data line without full parsing
        
        Args:
            data_line: Data line
            
        Returns:
            Tag ID or None if invalid
        """
        match = self.tag_pattern.match(data_line.strip())
        if match:
            return match.group(1).lower()
        return None

class TagDataBuffer:
    """Buffer for handling streaming tag data"""
    
    def __init__(self, max_buffer_size: int = 1024):
        """
        Initialize data buffer
        
        Args:
            max_buffer_size: Maximum buffer size in bytes
        """
        self.buffer = ""
        self.max_buffer_size = max_buffer_size
        self.parser = TagDataParser()
        self.logger = logging.getLogger(__name__)
    
    def add_data(self, data: str) -> list:
        """
        Add data to buffer and return complete lines
        
        Args:
            data: New data to add
            
        Returns:
            List of complete lines ready for parsing
        """
        self.buffer += data
        
        # Check buffer size
        if len(self.buffer) > self.max_buffer_size:
            self.logger.warning("Buffer overflow, clearing buffer")
            self.buffer = self.buffer[-self.max_buffer_size//2:]  # Keep recent half
        
        # Extract complete lines
        lines = []
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            if line.strip():  # Skip empty lines
                lines.append(line.strip())
        
        return lines
    
    def parse_lines(self, lines: list) -> list:
        """
        Parse multiple lines of tag data
        
        Args:
            lines: List of data lines
            
        Returns:
            List of parsed tag data dictionaries
        """
        parsed_data = []
        for line in lines:
            parsed = self.parser.parse_tag_data(line)
            if parsed:
                parsed_data.append(parsed)
        
        return parsed_data
    
    def clear_buffer(self):
        """Clear the internal buffer"""
        self.buffer = ""

# Example usage and testing
if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Test parser
    parser = TagDataParser()
    
    # Test cases
    test_data = [
        "TAG,fa451f0755d8,197,20240503140059.456",
        "TAG,ab123c4567ef,200,20240503140100.123",
        "TAG,invalid_tag,201,20240503140101.789",  # Invalid - will fail
        "INVALID,fa451f0755d8,202,20240503140102.456",  # Invalid format
        "TAG,12def890abcd,203,20240503140103.000"
    ]
    
    print("Testing Tag Data Parser:")
    print("-" * 50)
    
    for data in test_data:
        print(f"Input: {data}")
        result = parser.parse_tag_data(data)
        if result:
            print(f"✓ Parsed: Tag {result['tag_id']}, CNT {result['cnt']}, "
                  f"Time {result['parsed_timestamp']}")
        else:
            print("✗ Failed to parse")
        print()
    
    # Test buffer
    print("Testing Tag Data Buffer:")
    print("-" * 50)
    
    buffer = TagDataBuffer()
    
    # Simulate partial data reception
    partial_data = "TAG,fa451f0755d8,197,202405031400"
    buffer.add_data(partial_data)
    print(f"Added partial: {partial_data}")
    
    # Complete the line
    remaining_data = "59.456\nTAG,ab123c4567ef,200,20240503140100.123\n"
    lines = buffer.add_data(remaining_data)
    print(f"Completed with: {remaining_data.strip()}")
    print(f"Extracted lines: {lines}")
    
    # Parse the lines
    parsed = buffer.parse_lines(lines)
    for p in parsed:
        print(f"Parsed: {p['tag_id']} - {p['cnt']}")