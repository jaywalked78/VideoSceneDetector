# Changelog

All notable changes to the VideoSceneDetector project will be documented in this file.

## [1.2.1] - 2025-03-30

### Fixed
- Fixed frame numbering in metadata to use 1-based indexing instead of 0-based indexing

## [1.2.0] - 2025-03-30

### Added
- Frame upload verification before sending webhooks
- Sample file validation to confirm Google Drive upload accessibility
- More detailed upload status reports and logging

### Changed
- Improved webhook triggering logic to ensure uploads are complete
- Enhanced error handling and reporting in frame upload process
- Added more detailed progress reporting for Google Drive uploads

### Fixed
- Fixed issue where frame processing webhooks were triggered before all uploads completed
- Added validation to prevent duplicate workflow triggering

## [1.1.0] - 2025-03-30

### Added
- Service account authentication for Google Drive
- Environment variables for service account configuration
- Webhook URL configuration via environment variables

### Changed
- Updated GoogleDriveService to prioritize service account credentials
- Modified `upload_frames_to_drive` to use the improved authentication method
- Improved error handling for Google Drive API calls
- Updated documentation in README

### Fixed
- Fixed an issue where frame processor webhook was skipped due to authentication failures

## [1.0.0] - 2025-03-25

### Added
- Initial release
- Video scene detection using FFmpeg
- Frame extraction at scene change points
- Google Drive integration for storing frames
- Webhook notification system
- API endpoints for processing local and Google Drive videos 