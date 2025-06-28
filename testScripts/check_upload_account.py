#!/usr/bin/env python3
"""
Check what files the upload service account has access to
"""

from app.utils.google_drive import GoogleDriveService

def main():
    print("🔍 Checking Upload Service Account Files")
    print("=" * 50)
    
    try:
        service = GoogleDriveService(operation_type='upload')
        print(f"Upload service connected successfully")
        
        # List files
        result = service.list_files(page_size=10)
        files = result.get('files', [])
        
        if not files:
            print("No files found in upload account")
        else:
            print(f"Found {len(files)} files in upload account:")
            for i, file in enumerate(files, 1):
                name = file.get('name', 'Unknown')
                file_id = file.get('id', 'Unknown')
                file_type = file.get('mimeType', 'Unknown')
                size = file.get('size', 'Unknown')
                print(f"{i}. {name}")
                print(f"   ID: {file_id}")
                print(f"   Type: {file_type}")
                print(f"   Size: {size} bytes")
                print()
                
    except Exception as e:
        print(f"Error checking upload account: {e}")

if __name__ == "__main__":
    main() 