#!/usr/bin/env python3
"""
Helper script to authenticate with Google Drive and generate the token file.
Run this script once to authenticate and create a token.pickle file.
"""

import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

def authenticate_drive():
    """
    Run the OAuth authentication flow and save the token
    """
    print("Starting Google Drive authentication flow")
    
    # Path to credentials file
    credentials_path = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")
    token_path = os.getenv("GOOGLE_TOKEN", "token.pickle")
    
    if not os.path.exists(credentials_path):
        print(f"Error: Credentials file not found at {credentials_path}")
        return False
    
    creds = None
    # Check if we have a token file
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            try:
                creds = pickle.load(token)
                print("Found existing token file")
            except Exception as e:
                print(f"Error loading token file: {str(e)}")
    
    # If there are no valid credentials, run the flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            print("Refreshed existing OAuth credentials")
        else:
            # Run the OAuth flow with a fixed port (8080)
            # IMPORTANT: This port must be registered in Google Cloud Console
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path,
                ['https://www.googleapis.com/auth/drive.readonly'],
                redirect_uri='http://localhost:8080'
            )
            creds = flow.run_local_server(port=8080)
            print("Successfully authenticated with Google Drive")
        
        # Save the credentials for the next run
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
            print(f"Saved OAuth token to {token_path}")
    
    # Test the credentials by listing files
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        results = drive_service.files().list(pageSize=5).execute()
        items = results.get('files', [])
        
        print("\nAuthentication successful! Here are some of your files:")
        if not items:
            print("No files found.")
        else:
            for item in items:
                print(f"- {item['name']} ({item['id']})")
                
        return True
    except Exception as e:
        print(f"Error testing Drive API: {str(e)}")
        return False

if __name__ == "__main__":
    authenticate_drive() 