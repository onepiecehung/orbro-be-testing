#!/usr/bin/env python3
"""
API Test Script for RTLS Tag Management System
Tests all API endpoints with various scenarios
"""

import requests
import json
import time
import sys
from typing import Dict, Any

class APITester:
    def __init__(self, base_url="http://localhost:8000"):
        """Initialize API tester"""
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def test_health_check(self):
        """Test health check endpoint"""
        print("🔍 Testing Health Check...")
        try:
            response = self.session.get(f"{self.base_url}/health")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health Status: {data['status']}")
                print(f"   Uptime: {data.get('uptime', 'N/A')}")
                print(f"   Active Tags: {data.get('active_tags', 0)}")
                print(f"   Total Processed: {data.get('total_processed', 0)}")
                return True
            else:
                print(f"❌ Health check failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
    
    def test_register_tags(self):
        """Test tag registration"""
        print("\n📝 Testing Tag Registration...")
        
        test_tags = [
            {"id": "fa451f0755d8", "description": "Helmet Tag for worker A"},
            {"id": "ab123c4567ef", "description": "Safety Vest Tag for worker B"},
            {"id": "12def890abcd", "description": "Tool Tag Station 1"},
            {"id": "98765fedcba0", "description": "Emergency Exit Tag"},
        ]
        
        registered_count = 0
        
        for tag in test_tags:
            try:
                response = self.session.post(
                    f"{self.base_url}/tags",
                    json=tag
                )
                
                print(f"Registering {tag['id']}: Status {response.status_code}")
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    print(f"✅ {data['message']}")
                    registered_count += 1
                else:
                    print(f"❌ Registration failed: {response.text}")
                    
            except Exception as e:
                print(f"❌ Registration error for {tag['id']}: {e}")
        
        print(f"📊 Successfully registered {registered_count}/{len(test_tags)} tags")
        return registered_count > 0
    
    def test_invalid_registrations(self):
        """Test invalid tag registrations"""
        print("\n🚫 Testing Invalid Registrations...")
        
        invalid_tags = [
            {"id": "invalid_hex_ZZZZ", "description": "Invalid hex characters"},
            {"id": "", "description": "Empty tag ID"},
            {"id": "valid123", "description": ""},  # Empty description should be allowed
        ]
        
        for tag in invalid_tags:
            try:
                response = self.session.post(
                    f"{self.base_url}/tags",
                    json=tag
                )
                
                print(f"Testing invalid tag {tag['id']}: Status {response.status_code}")
                
                if response.status_code >= 400:
                    print("✅ Correctly rejected invalid tag")
                else:
                    print(f"⚠️  Unexpectedly accepted invalid tag: {response.json()}")
                    
            except Exception as e:
                print(f"❌ Error testing invalid tag: {e}")
    
    def test_get_all_tags(self):
        """Test getting all tags"""
        print("\n📋 Testing Get All Tags...")
        
        try:
            response = self.session.get(f"{self.base_url}/tags")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Retrieved {len(data)} tags")
                
                for tag in data:
                    print(f"   📌 {tag['id']}: {tag['description']}")
                    print(f"      Last CNT: {tag.get('last_cnt', 'N/A')}")
                    print(f"      Last Seen: {tag.get('last_seen', 'N/A')}")
                    print(f"      Updates: {tag.get('total_updates', 0)}")
                
                return len(data) > 0
            else:
                print(f"❌ Failed to get tags: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error getting all tags: {e}")
            return False
    
    def test_get_specific_tag(self, tag_id="fa451f0755d8"):
        """Test getting specific tag status"""
        print(f"\n🎯 Testing Get Specific Tag ({tag_id})...")
        
        try:
            response = self.session.get(f"{self.base_url}/tag/{tag_id}")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Tag Details:")
                print(f"   ID: {data['id']}")
                print(f"   Description: {data['description']}")
                print(f"   Last CNT: {data.get('last_cnt', 'N/A')}")
                print(f"   Last Seen: {data.get('last_seen', 'N/A')}")
                print(f"   Total Updates: {data.get('total_updates', 0)}")
                print(f"   Is Registered: {data['is_registered']}")
                return True
            elif response.status_code == 404:
                print(f"✅ Correctly returned 404 for unregistered tag")
                return True
            else:
                print(f"❌ Unexpected response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error getting specific tag: {e}")
            return False
    
    def test_unregistered_tag(self):
        """Test getting status of unregistered tag"""
        print("\n❓ Testing Unregistered Tag...")
        
        unregistered_id = "nonexistent123"
        
        try:
            response = self.session.get(f"{self.base_url}/tag/{unregistered_id}")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 404:
                print("✅ Correctly returned 404 for unregistered tag")
                return True
            else:
                print(f"⚠️  Unexpected status for unregistered tag: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing unregistered tag: {e}")
            return False
    
    def test_detailed_stats(self):
        """Test detailed statistics endpoint"""
        print("\n📊 Testing Detailed Statistics...")
        
        try:
            response = self.session.get(f"{self.base_url}/stats")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Statistics Retrieved:")
                print(f"   Registered Tags: {data.get('registered_tags', 0)}")
                print(f"   Active Tags: {data.get('active_tags', 0)}")
                print(f"   Uptime: {data.get('uptime', 'N/A')}")
                
                processor_stats = data.get('processor_stats', {})
                if processor_stats:
                    print(f"   Processor Stats:")
                    print(f"     Total Received: {processor_stats.get('total_received', 0)}")
                    print(f"     Total Processed: {processor_stats.get('total_processed', 0)}")
                    print(f"     Total Errors: {processor_stats.get('total_errors', 0)}")
                
                return True
            else:
                print(f"❌ Failed to get stats: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            return False
    
    def test_tag_unregistration(self, tag_id="98765fedcba0"):
        """Test tag unregistration"""
        print(f"\n🗑️  Testing Tag Unregistration ({tag_id})...")
        
        try:
            response = self.session.delete(f"{self.base_url}/tag/{tag_id}")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ {data['message']}")
                
                # Verify tag is no longer registered
                get_response = self.session.get(f"{self.base_url}/tag/{tag_id}")
                if get_response.status_code == 404:
                    print("✅ Confirmed tag is unregistered")
                    return True
                else:
                    print("⚠️  Tag still appears to be registered")
                    return False
            else:
                print(f"❌ Failed to unregister: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error unregistering tag: {e}")
            return False
    
    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting RTLS API Tests")
        print("=" * 60)
        
        tests = [
            ("Health Check", self.test_health_check),
            ("Tag Registration", self.test_register_tags),
            ("Invalid Registrations", self.test_invalid_registrations),
            ("Get All Tags", self.test_get_all_tags),
            ("Get Specific Tag", self.test_get_specific_tag),
            ("Unregistered Tag", self.test_unregistered_tag),
            ("Detailed Statistics", self.test_detailed_stats),
            ("Tag Unregistration", self.test_tag_unregistration),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n{'='*60}")
            print(f"🧪 Running: {test_name}")
            print(f"{'='*60}")
            
            try:
                if test_func():
                    passed += 1
                    print(f"✅ {test_name} PASSED")
                else:
                    print(f"❌ {test_name} FAILED")
                    
                time.sleep(1)  # Small delay between tests
                
            except Exception as e:
                print(f"❌ {test_name} ERROR: {e}")
        
        print(f"\n{'='*60}")
        print(f"📊 TEST RESULTS: {passed}/{total} tests passed")
        print(f"{'='*60}")
        
        return passed == total

def test_with_curl_examples():
    """Print curl command examples"""
    print("\n🔧 CURL Command Examples:")
    print("=" * 60)
    
    examples = [
        ("Health Check", "curl http://localhost:8000/health"),
        ("Register Tag", 'curl -X POST http://localhost:8000/tags -H "Content-Type: application/json" -d \'{"id": "fa451f0755d8", "description": "Helmet Tag for worker A"}\''),
        ("Get All Tags", "curl http://localhost:8000/tags"),
        ("Get Specific Tag", "curl http://localhost:8000/tag/fa451f0755d8"),
        ("Get Statistics", "curl http://localhost:8000/stats"),
        ("Unregister Tag", "curl -X DELETE http://localhost:8000/tag/fa451f0755d8"),
    ]
    
    for name, command in examples:
        print(f"\n📌 {name}:")
        print(f"   {command}")

def main():
    """Main function"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "curl":
            test_with_curl_examples()
            return
        elif sys.argv[1] == "quick":
            # Quick test mode
            tester = APITester()
            tester.test_health_check()
            tester.test_register_tags()
            tester.test_get_all_tags()
            return
    
    # Full test suite
    print("RTLS API Test Suite")
    print("Make sure the API server is running on http://localhost:8000")
    print("Start with: uvicorn api:app --reload --host 0.0.0.0 --port 8000")
    
    input("\nPress Enter to continue with tests...")
    
    tester = APITester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed. Check the output above.")
    
    print("\nFor curl examples, run: python test_api.py curl")

if __name__ == "__main__":
    main()