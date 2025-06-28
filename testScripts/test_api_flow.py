#!/usr/bin/env python3
"""
Test script that replicates the exact API flow to debug authentication issues
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_api_authentication_flow(download_account_type="secondary"):
    """
    Test the exact same flow that the API uses
    """
    print(f"🧪 Testing API Authentication Flow")
    print(f"Download Account Type: {download_account_type}")
    print("=" * 60)
    
    try:
        # Step 1: Import the GoogleDriveService (same as API)
        print("📦 Step 1: Importing GoogleDriveService...")
        from app.utils.google_drive import GoogleDriveService
        print("✅ Import successful")
        
        # Step 2: Determine operation type (same logic as API)
        print(f"\n🔧 Step 2: Determining operation type...")
        download_operation_type = "download_primary" if download_account_type == "primary" else "download_secondary"
        print(f"Operation type: {download_operation_type}")
        
        # Step 3: Create the service (same as API)
        print(f"\n🚀 Step 3: Creating GoogleDriveService...")
        drive_service = GoogleDriveService(operation_type=download_operation_type)
        print("✅ GoogleDriveService created successfully")
        
        # Step 4: Test file validation (same as API)
        print(f"\n🔍 Step 4: Testing file validation...")
        test_file_id = "1X9SSekqD4oX98Ca5uQ17iQj4BZOb-z0-"  # Your test file
        
        try:
            file_metadata = drive_service.get_file_metadata(test_file_id)
            print(f"✅ File validation successful!")
            print(f"   File name: {file_metadata.get('name', 'Unknown')}")
            print(f"   File type: {file_metadata.get('mimeType', 'Unknown')}")
            return True
            
        except Exception as e:
            print(f"❌ File validation failed: {e}")
            print(f"   Error type: {type(e).__name__}")
            return False
            
    except Exception as e:
        print(f"❌ Authentication flow failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False

def test_both_account_types():
    """
    Test both primary and secondary account types
    """
    print("🔄 Testing Both Account Types")
    print("=" * 60)
    
    # Test secondary account
    print("\n1️⃣ Testing Secondary Account...")
    secondary_success = test_api_authentication_flow("secondary")
    
    print("\n" + "-" * 40)
    
    # Test primary account  
    print("\n2️⃣ Testing Primary Account...")
    primary_success = test_api_authentication_flow("primary")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Secondary account: {'✅ PASS' if secondary_success else '❌ FAIL'}")
    print(f"Primary account: {'✅ PASS' if primary_success else '❌ FAIL'}")
    
    if secondary_success and primary_success:
        print("\n🎉 Both accounts working! The issue might be elsewhere.")
    elif secondary_success:
        print("\n⚠️ Only secondary account working. Check primary account setup.")
    elif primary_success:
        print("\n⚠️ Only primary account working. Check secondary account setup.")
    else:
        print("\n❌ Both accounts failing. Check your credential setup.")

def check_environment_variables():
    """
    Check all relevant environment variables
    """
    print("🌍 Environment Variables Check")
    print("=" * 60)
    
    vars_to_check = [
        "GOOGLE_DOWNLOAD_USE_SERVICE_ACCOUNT",
        "GOOGLE_DOWNLOAD_SERVICE_ACCOUNT_FILE", 
        "GOOGLE_DOWNLOAD_CREDENTIALS",
        "GOOGLE_UPLOAD_USE_SERVICE_ACCOUNT",
        "GOOGLE_UPLOAD_SERVICE_ACCOUNT_FILE",
        "GOOGLE_UPLOAD_CREDENTIALS",
        "DEBUG_MODE"
    ]
    
    for var in vars_to_check:
        value = os.getenv(var, "NOT SET")
        print(f"{var}: {value}")
        
        # Check file existence for file paths
        if "FILE" in var and value != "NOT SET":
            expanded_path = os.path.expanduser(value)
            exists = os.path.exists(expanded_path)
            print(f"  → File exists: {exists}")
            if not exists:
                print(f"  → Expanded path: {expanded_path}")

if __name__ == "__main__":
    # Check environment first
    check_environment_variables()
    
    print("\n")
    
    # Test the authentication flow
    test_both_account_types()
    
    print("\n🔧 Next Steps:")
    print("- If this test passes but the API fails, the issue is in the server environment")
    print("- If this test fails, the issue is with your credential setup")
    print("- Check that your server is loading the .env file correctly")
    print("- Restart your server after making .env changes") 