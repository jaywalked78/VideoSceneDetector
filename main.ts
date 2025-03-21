import { memoryManager } from './utils/memoryManager';
import { VideoProcessorService } from './services/videoProcessor';

async function bootstrap() {
  // Initialize memory manager
  memoryManager.startMonitoring();
  
  // Log initial memory status
  const initialMemory = memoryManager.getMemoryUsage();
  console.log(`Initial memory usage: ${initialMemory.usagePercentage.toFixed(2)}%`);
  console.log(`Memory threshold set to: ${memoryManager.maxUsagePercentage}%`);

  const app = await NestFactory.create(AppModule);
  
  // Initialize the video processor service
  const videoProcessorService = app.get(VideoProcessorService);
  
  // Log that progress display is enabled
  console.log('FFMPEG progress display enabled. Video processing will show progress in this terminal.');
  
  await app.listen(3000);
}

bootstrap(); 