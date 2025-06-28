#!/usr/bin/env python3
"""
Debug script to test Google Drive credential loading
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def debug_credentials():
    print("🔍 Debugging Google Drive Credentials")
    print("=" * 50)
    
    # Check environment variables
    print("\n📋 Environment Variables:")
    download_use_sa = os.getenv("GOOGLE_DOWNLOAD_USE_SERVICE_ACCOUNT", "")
    download_sa_file = os.getenv("GOOGLE_DOWNLOAD_SERVICE_ACCOUNT_FILE", "")
    download_credentials = os.getenv("GOOGLE_DOWNLOAD_CREDENTIALS", "")
    
    print(f"GOOGLE_DOWNLOAD_USE_SERVICE_ACCOUNT: {download_use_sa}")
    print(f"GOOGLE_DOWNLOAD_SERVICE_ACCOUNT_FILE: {download_sa_file}")
    print(f"GOOGLE_DOWNLOAD_CREDENTIALS: {download_credentials}")
    
    # Check file paths
    print("\n📁 File Path Analysis:")
    
    # Expand paths
    if download_sa_file:
        expanded_sa_file = os.path.expanduser(download_sa_file)
        print(f"Service Account File (original): {download_sa_file}")
        print(f"Service Account File (expanded): {expanded_sa_file}")
        print(f"Service Account File exists: {os.path.exists(expanded_sa_file)}")
        
        if os.path.exists(expanded_sa_file):
            try:
                with open(expanded_sa_file, 'r') as f:
                    import json
                    data = json.load(f)
                    print(f"Service Account File type: {data.get('type', 'unknown')}")
                    print(f"Service Account Project ID: {data.get('project_id', 'unknown')}")
            except Exception as e:
                print(f"Error reading service account file: {e}")
    
    if download_credentials:
        expanded_credentials = os.path.expanduser(download_credentials)
        print(f"\nCredentials File (original): {download_credentials}")
        print(f"Credentials File (expanded): {expanded_credentials}")
        print(f"Credentials File exists: {os.path.exists(expanded_credentials)}")
        
        if os.path.exists(expanded_credentials):
            try:
                with open(expanded_credentials, 'r') as f:
                    import json
                    data = json.load(f)
                    if 'installed' in data:
                        print(f"Credentials File type: OAuth Client")
                    elif 'type' in data:
                        print(f"Credentials File type: {data.get('type')}")
                    else:
                        print(f"Credentials File type: Unknown")
            except Exception as e:
                print(f"Error reading credentials file: {e}")
    
    # Test GoogleDriveService initialization
    print("\n🚀 Testing GoogleDriveService Initialization:")
    try:
        from app.utils.google_drive import GoogleDriveService
        
        print("Attempting to create download_secondary service...")
        try:
            service = GoogleDriveService(operation_type="download_secondary")
            print("✅ SUCCESS: download_secondary service created")
            
            # Test a simple API call
            try:
                # Just try to list 1 file to test the connection
                service.drive_service.files().list(pageSize=1).execute()
                print("✅ SUCCESS: API connection test passed")
            except Exception as e:
                print(f"❌ FAILED: API connection test failed: {e}")
                
        except Exception as e:
            print(f"❌ FAILED: download_secondary service creation failed: {e}")
            
    except ImportError as e:
        print(f"❌ IMPORT ERROR: {e}")
    
    print("\n🔧 Debugging Steps:")
    print("1. Check if the file paths are correct")
    print("2. Verify the service account file has the right permissions")
    print("3. Make sure the service account has Google Drive API access")
    print("4. Check if the project has the Drive API enabled")

if __name__ == "__main__":
    debug_credentials() 