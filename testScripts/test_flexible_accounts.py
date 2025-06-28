#!/usr/bin/env python3
"""
Test script for flexible Google Drive account functionality.
Tests both primary and secondary account downloads.
"""

import requests
import json
import sys
import time

# API endpoint
API_URL = "http://localhost:8000"

def test_download_account_type(file_id: str, account_type: str = "secondary"):
    """
    Test downloading from a specific account type
    
    Args:
        file_id: Google Drive file ID to test with
        account_type: "primary" or "secondary"
    """
    print(f"\n{'='*50}")
    print(f"Testing download with {account_type} account")
    print(f"{'='*50}")
    
    payload = {
        "file_id": file_id,
        "destination_folder": "/tmp/test_downloads",
        "callback_url": "http://localhost:8000/test-callback",  # Dummy callback
        "scene_threshold": 0.4,
        "create_subfolder": True,
        "delete_after_processing": False,
        "force_download": True,  # Force download to test credentials
        "download_account_type": account_type
    }
    
    try:
        print(f"Sending request to {API_URL}/video/process-drive-video")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            f"{API_URL}/video/process-drive-video",
            json=payload,
            timeout=10
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"✅ SUCCESS: {account_type} account download initiated successfully!")
                return True
            else:
                print(f"❌ FAILED: {result.get('message', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP ERROR: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)}")
        return False

def test_credentials_validation():
    """
    Test that the Google Drive services initialize correctly with different operation types
    """
    print(f"\n{'='*50}")
    print("Testing credential initialization")
    print(f"{'='*50}")
    
    try:
        from app.utils.google_drive import GoogleDriveService
        
        # Test secondary account credentials
        print("Testing secondary account credentials...")
        try:
            secondary_service = GoogleDriveService(operation_type="download_secondary")
            print("✅ Secondary account service initialized successfully")
        except Exception as e:
            print(f"❌ Secondary account failed: {str(e)}")
        
        # Test primary account credentials  
        print("Testing primary account credentials...")
        try:
            primary_service = GoogleDriveService(operation_type="download_primary")
            print("✅ Primary account service initialized successfully")
        except Exception as e:
            print(f"❌ Primary account failed: {str(e)}")
            
        # Test upload credentials
        print("Testing upload credentials...")
        try:
            upload_service = GoogleDriveService(operation_type="upload")
            print("✅ Upload service initialized successfully")
        except Exception as e:
            print(f"❌ Upload service failed: {str(e)}")
            
    except ImportError as e:
        print(f"❌ Cannot import GoogleDriveService: {str(e)}")
        print("Make sure you're running this from the project root directory")

def main():
    """
    Main test function
    """
    print("🧪 Testing Flexible Google Drive Account Functionality")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("❌ ERROR: Please provide a Google Drive file ID to test with")
        print("Usage: python test_flexible_accounts.py <file_id>")
        print("\nExample: python test_flexible_accounts.py 1X9SSekqD4oX98Ca5uQ17iQj4BZOb-z0-")
        print("\nThis will test downloading the same file from both primary and secondary accounts")
        return
    
    file_id = sys.argv[1]
    print(f"Testing with file ID: {file_id}")
    
    # Test credential initialization
    test_credentials_validation()
    
    # Test with secondary account (default)
    secondary_success = test_download_account_type(file_id, "secondary")
    
    # Wait a bit between tests
    time.sleep(2)
    
    # Test with primary account
    primary_success = test_download_account_type(file_id, "primary")
    
    # Summary
    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print(f"{'='*50}")
    print(f"Secondary account download: {'✅ PASS' if secondary_success else '❌ FAIL'}")
    print(f"Primary account download: {'✅ PASS' if primary_success else '❌ FAIL'}")
    
    if secondary_success and primary_success:
        print("\n🎉 All tests passed! Your flexible account setup is working correctly.")
    elif secondary_success or primary_success:
        print("\n⚠️ Partial success. Check your credential configuration.")
    else:
        print("\n❌ All tests failed. Please check your server and credential setup.")
    
    print("\nTips:")
    print("- Make sure your server is running on localhost:8000")
    print("- Ensure both primary and secondary account credentials are properly configured")
    print("- Check the server logs for detailed error information")
    print("- Verify that the test file exists in both Google accounts (if testing both)")

if __name__ == "__main__":
    main() 