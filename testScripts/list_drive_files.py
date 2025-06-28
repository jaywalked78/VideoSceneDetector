#!/usr/bin/env python3
"""
List files from both Google Drive accounts to find valid file IDs
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def list_files_from_account(account_type="secondary", max_files=10):
    """
    List files from the specified account
    """
    print(f"\n📁 Listing files from {account_type} account...")
    
    try:
        from app.utils.google_drive import GoogleDriveService
        
        # Determine operation type
        operation_type = "download_primary" if account_type == "primary" else "download_secondary"
        
        # Create service
        service = GoogleDriveService(operation_type=operation_type)
        
        # List files
        result = service.list_files(page_size=max_files)
        files = result.get('files', [])
        
        if not files:
            print(f"   No files found in {account_type} account")
            return []
        
        print(f"   Found {len(files)} files:")
        file_ids = []
        
        for i, file in enumerate(files, 1):
            file_id = file.get('id', 'No ID')
            file_name = file.get('name', 'No name')
            file_type = file.get('mimeType', 'Unknown type')
            file_size = file.get('size', 'Unknown size')
            
            print(f"   {i}. {file_name}")
            print(f"      ID: {file_id}")
            print(f"      Type: {file_type}")
            print(f"      Size: {file_size} bytes")
            print()
            
            file_ids.append(file_id)
        
        return file_ids
        
    except Exception as e:
        print(f"   ❌ Error listing files from {account_type} account: {e}")
        return []

def main():
    print("📋 Google Drive File Listing Tool")
    print("=" * 50)
    
    # List files from secondary account
    secondary_files = list_files_from_account("secondary", 5)
    
    # List files from primary account  
    primary_files = list_files_from_account("primary", 5)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    
    if secondary_files:
        print(f"✅ Secondary account: {len(secondary_files)} files found")
        print(f"   Test with: {secondary_files[0]}")
    else:
        print("❌ Secondary account: No files found")
    
    if primary_files:
        print(f"✅ Primary account: {len(primary_files)} files found")
        print(f"   Test with: {primary_files[0]}")
    else:
        print("❌ Primary account: No files found")
    
    # Test suggestions
    print("\n🧪 Testing Suggestions:")
    if secondary_files:
        print(f"Test secondary account download:")
        print(f'  curl -X POST http://localhost:8000/video/process-drive-video \\')
        print(f'    -H "Content-Type: application/json" \\')
        print(f'    -d \'{{"file_id": "{secondary_files[0]}", "download_account_type": "secondary"}}\'')
    
    if primary_files:
        print(f"\nTest primary account download:")
        print(f'  curl -X POST http://localhost:8000/video/process-drive-video \\')
        print(f'    -H "Content-Type: application/json" \\')
        print(f'    -d \'{{"file_id": "{primary_files[0]}", "download_account_type": "primary"}}\'')

if __name__ == "__main__":
    main() 