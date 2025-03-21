/**
 * Get file metadata from Google Drive
 * @param fileId Google Drive file ID
 */
@backoff.on_exception(
  backoff.expo,
  googleapiclient.errors.HttpError,
  max_tries=3
)
async def get_file_metadata(self, fileId: str) -> Dict[str, Any]:
    """Get metadata for a file in Google Drive."""
    fileId = fileId.strip()  # Remove any whitespace
    
    # Remove trailing period if present (common error in file IDs)
    if fileId.endswith('.'):
        logger.warning(f"Removing trailing period from file ID: {fileId}")
        fileId = fileId[:-1]
    
    logger.info(f"Getting metadata for file ID: {fileId}")
    
    try:
        return self.service.files().get(
            fileId=fileId,
            fields="id, name, mimeType, size, modifiedTime, createdTime"
        ).execute()
    except googleapiclient.errors.HttpError as error:
        if error.resp.status == 404:
            logger.error(f"Error getting file metadata for file ID {fileId}: {error}")
            logger.error("File not found. This could be due to:")
            logger.error("1. The file ID is incorrect")
            logger.error("2. The file has been deleted")
            logger.error("3. You don't have permission to access this file")
            logger.error(f"Please verify the file ID and permissions: {fileId}")
        else:
            logger.error(f"Error getting file metadata for file ID {fileId}: {error}")
        
        raise 