#!/usr/bin/env python3
"""
Verify which Google account each credential set is connecting to
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_account_info(operation_type):
    """
    Get account information for a specific operation type
    """
    try:
        from app.utils.google_drive import GoogleDriveService
        
        print(f"\n🔍 Testing {operation_type}...")
        
        # Create service
        service = GoogleDriveService(operation_type=operation_type)
        
        # Get account info by trying to access the 'about' endpoint
        about_info = service.drive_service.about().get(fields="user").execute()
        user_info = about_info.get('user', {})
        
        email = user_info.get('emailAddress', 'Unknown')
        display_name = user_info.get('displayName', 'Unknown')
        
        print(f"  ✅ Connected to: {email} ({display_name})")
        return email
        
    except Exception as e:
        print(f"  ❌ Failed to connect: {e}")
        return None

def main():
    print("🔍 Google Drive Account Verification")
    print("=" * 50)
    
    # Test both credential sets
    primary_email = get_account_info("download_primary")
    secondary_email = get_account_info("download_secondary")
    upload_email = get_account_info("upload")
    
    print("\n" + "=" * 50)
    print("📊 Account Mapping Summary")
    print("=" * 50)
    
    print(f"download_primary connects to: {primary_email or 'FAILED'}")
    print(f"download_secondary connects to: {secondary_email or 'FAILED'}")
    print(f"upload connects to: {upload_email or 'FAILED'}")
    
    print("\n📋 Expected Mapping:")
    print("download_primary should connect to: jaywalked78@gmail.com")
    print("download_secondary should connect to: jason.cox7858@gmail.com")
    print("upload should connect to: jaywalked78@gmail.com")
    
    print("\n🎯 File Location Analysis:")
    print("File 1X9SSekqD4oX98Ca5uQ17iQj4BZOb-z0- is owned by: jason.cox7858@gmail.com")
    if secondary_email == "jason.cox7858@gmail.com":
        print("✅ Use 'download_account_type': 'secondary' to access this file")
    elif primary_email == "jason.cox7858@gmail.com":
        print("✅ Use 'download_account_type': 'primary' to access this file")
    else:
        print("❌ Neither credential set connects to jason.cox7858@gmail.com!")
        print("   This explains why the file is not found.")

if __name__ == "__main__":
    main() 