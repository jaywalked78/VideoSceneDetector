import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';

async function testOutputCheck() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    console.error('Please provide a video path');
    console.log('Usage: ts-node scripts/test-output-check.ts /path/to/video.mp4');
    process.exit(1);
  }
  
  const videoPath = args[0];
  console.log(`Testing output check for: ${videoPath}`);
  
  // Create some dummy output to test with
  const outputDir = path.join(
    path.dirname(videoPath),
    `${path.basename(videoPath, path.extname(videoPath))}_frames`
  );
  
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
    // Create a dummy frame file
    fs.writeFileSync(path.join(outputDir, 'frame_0001.jpg'), 'dummy frame');
    console.log(`Created dummy output at: ${outputDir}`);
  }
  
  try {
    // Test the check-output endpoint
    const checkResponse = await axios.get(
      `http://localhost:3000/video/check-output/${encodeURIComponent(outputDir)}`
    );
    console.log('Check output response:', checkResponse.data);
    
    // Test the extract-frames endpoint (should detect existing frames)
    const extractResponse = await axios.post('http://localhost:3000/video/extract-frames', {
      inputPath: videoPath,
      outputDir
    });
    console.log('Extract frames response:', extractResponse.data);
    
  } catch (error) {
    console.error('Error:', error.message);
  }
}

testOutputCheck(); 