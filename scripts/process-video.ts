import axios from 'axios';

async function processVideo() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    console.error('Please provide a video path');
    console.log('Usage: ts-node scripts/process-video.ts /path/to/video.mp4');
    process.exit(1);
  }
  
  const videoPath = args[0];
  console.log(`Requesting video processing for: ${videoPath}`);
  
  try {
    const response = await axios.get(`http://localhost:3000/video/test-progress/${encodeURIComponent(videoPath)}`);
    console.log('Server response:', response.data);
  } catch (error) {
    console.error('Error:', error.message);
  }
}

processVideo(); 