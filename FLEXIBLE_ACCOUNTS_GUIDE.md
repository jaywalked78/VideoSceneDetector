# Flexible Google Drive Account Guide

This guide explains how to use the new flexible Google Drive account functionality that allows you to download from either your primary or secondary account while always uploading to your primary account.

## Overview

The system now supports:
- **Primary Account**: Your main Google Drive account (for uploads and optionally downloads)
- **Secondary Account**: An alternative Google Drive account (for downloads when primary is full)
- **Flexible Downloads**: Choose which account to download from per request
- **Consistent Uploads**: Always uploads processed frames to your primary account

## Configuration

### Environment Variables

Your `.env` file should include credentials for both accounts:

```env
# Google Drive Download Configuration (Secondary Account)
GOOGLE_DOWNLOAD_CREDENTIALS=download_credentials.json
GOOGLE_DOWNLOAD_SERVICE_ACCOUNT_FILE=~/Documents/VideoSceneDetector/serviceAccountAuth/secondary-account.json
GOOGLE_DOWNLOAD_USE_SERVICE_ACCOUNT=true

# Google Drive Upload Configuration (Primary Account)
GOOGLE_UPLOAD_CREDENTIALS=credentials.json
GOOGLE_UPLOAD_SERVICE_ACCOUNT_FILE=~/Documents/VideoSceneDetector/serviceAccountAuth/primary-account.json
GOOGLE_UPLOAD_USE_SERVICE_ACCOUNT=true
```

### Credential Files

You'll need to set up service account credentials for both accounts:

1. **Primary Account Credentials** (`primary-account.json`):
   - Your main Google account where processed frames are stored
   - Needs access to the "ScreenRecorded Frames" folder
   - Used for uploads and primary downloads

2. **Secondary Account Credentials** (`secondary-account.json`):
   - Your alternative Google account for storing source videos
   - Used when your primary account runs out of space
   - Used for secondary downloads

## API Usage

### Downloading from Secondary Account (Default)

```json
{
  "file_id": "1X9SSekqD4oX98Ca5uQ17iQj4BZOb-z0-",
  "destination_folder": "/home/videos/screenRecordings",
  "callback_url": "http://localhost:5678/webhook/callback",
  "download_account_type": "secondary"
}
```

### Downloading from Primary Account

```json
{
  "file_id": "1X9SSekqD4oX98Ca5uQ17iQj4BZOb-z0-",
  "destination_folder": "/home/videos/screenRecordings", 
  "callback_url": "http://localhost:5678/webhook/callback",
  "download_account_type": "primary"
}
```

### Default Behavior

If you don't specify `download_account_type`, it defaults to `"secondary"` to maintain compatibility with your current setup.

## Use Cases

### Current Setup (Secondary Downloads)
When your primary account is full:
```json
{
  "file_id": "file-in-secondary-account",
  "download_account_type": "secondary"
}
```

### Future Setup (After Storage Upgrade)
When you upgrade your primary account storage:
```json
{
  "file_id": "file-in-primary-account", 
  "download_account_type": "primary"
}
```

### Mixed Environment
You can use both accounts simultaneously:
- Store new large videos in secondary account
- Keep important videos in primary account
- Choose the appropriate download source per request

## Testing

Use the provided test script to verify your setup:

```bash
python test_flexible_accounts.py <file_id>
```

This will test downloading the same file using both account types and verify your credentials are working correctly.

## Migration Strategy

1. **Current State**: Use secondary account for downloads, primary for uploads
2. **Transition**: Gradually move files back to primary account as storage allows
3. **Future State**: Use primary account for both downloads and uploads

## Troubleshooting

### Common Issues

1. **File Not Found (404)**: 
   - The file exists in one account but you're trying to download from the other
   - Check which account contains the file and set `download_account_type` accordingly

2. **Authentication Errors**:
   - Verify both credential files exist and are valid
   - Check environment variable paths are correct
   - Ensure service accounts have appropriate permissions

3. **Permission Errors**:
   - Secondary account needs read access to source files
   - Primary account needs write access to destination folder

### Debugging

Check the server logs for detailed information about which credentials are being used:

```
Initializing GoogleDriveService for download_secondary operations using secondary account credentials
```

The logs will show which account type is being used for each operation.

## Best Practices

1. **Organize by Account**: Keep related files in the same account when possible
2. **Test Credentials**: Regularly test both sets of credentials
3. **Monitor Usage**: Track which account is being used for downloads
4. **Plan Migration**: Have a strategy for eventually consolidating to one account
5. **Backup Credentials**: Keep secure backups of both credential files

## API Reference

### Request Parameters

- `download_account_type` (optional): `"primary"` or `"secondary"`
  - Default: `"secondary"`
  - Determines which Google account to use for downloading files

### Environment Variables

- `GOOGLE_DOWNLOAD_*`: Secondary account credentials for downloads
- `GOOGLE_UPLOAD_*`: Primary account credentials for uploads
- `GOOGLE_*`: Legacy/fallback credentials (used for primary operations if upload-specific vars not set)

This flexible setup gives you the best of both worlds: immediate relief from storage constraints while maintaining a clear path forward for future consolidation. 