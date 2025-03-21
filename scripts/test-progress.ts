import { executeFFmpegWithProgress, formatProgressBar } from '../utils/ffmpegProgress';
import { getVideoDurationInSeconds } from 'get-video-duration';

async function testProgressDisplay(videoPath: string): Promise<void> {
  try {
    console.log(`Testing progress display with video: ${videoPath}`);
    
    // Get video duration
    const duration = await getVideoDurationInSeconds(videoPath);
    console.log(`Video duration: ${duration.toFixed(2)} seconds`);
    
    // Define a simple FFMPEG operation (e.g., converting format)
    const outputPath = `${videoPath}.test.mp4`;
    const ffmpegArgs = [
      '-i', videoPath,
      '-c:v', 'libx264',
      '-preset', 'ultrafast', // Use ultrafast for quick testing
      '-c:a', 'aac',
      outputPath
    ];
    
    console.log('Starting FFMPEG with progress tracking...');
    console.log('Progress display should appear below:');
    
    // Execute with progress tracking
    await executeFFmpegWithProgress(ffmpegArgs, {
      duration,
      onProgress: (progress) => {
        // Clear current line and print progress bar
        process.stdout.write('\r\x1b[K');
        process.stdout.write(
          `${formatProgressBar(progress.progress)} | FPS: ${progress.fps || 0} | Speed: ${progress.speed || 'N/A'}`
        );
      },
      onComplete: () => {
        process.stdout.write('\n');
        console.log('Processing complete!');
        console.log(`Output saved to: ${outputPath}`);
      },
      onError: (error) => {
        console.error(`Error during processing: ${error.message}`);
      }
    });
    
  } catch (error) {
    console.error('Test failed:', error);
  }
}

// Get video path from command line arguments
const videoPath = process.argv[2];
if (!videoPath) {
  console.error('Please provide a video path as an argument');
  console.log('Usage: ts-node scripts/test-progress.ts /path/to/your/video.mp4');
  process.exit(1);
}

testProgressDisplay(videoPath); 