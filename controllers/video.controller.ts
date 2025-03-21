import { VideoProcessorService } from '../services/videoProcessor';
import { Controller, Post, Body, Get, Param } from '@nestjs/common';
import * as path from 'path';

@Controller('video')
export class VideoController {
  constructor(private readonly videoProcessorService: VideoProcessorService) {}

  @Get('queue-status')
  getQueueStatus() {
    return this.videoProcessorService.getQueueStatus();
  }
  
  @Post('process')
  async processVideo(@Body() data: { 
    inputPath: string, 
    outputPath: string 
  }) {
    console.log(`Received request to process video: ${data.inputPath} -> ${data.outputPath}`);
    
    try {
      const result = await this.videoProcessorService.processVideo(
        data.inputPath,
        data.outputPath
      );
      
      return { 
        success: result,
        message: result ? 'Video processing completed' : 'Video processing failed'
      };
    } catch (error) {
      return {
        success: false,
        message: `Error: ${error.message}`
      };
    }
  }
  
  @Get('test-progress/:videoPath')
  async testProgress(@Param('videoPath') videoPath: string) {
    console.log(`Testing progress display with video: ${videoPath}`);
    
    // Create a test output path
    const outputPath = `${videoPath}.processed.mp4`;
    
    // Process the video with progress display
    const result = await this.videoProcessorService.processVideo(
      videoPath,
      outputPath
    );
    
    return { 
      success: result,
      message: result ? 'Progress test completed successfully' : 'Progress test failed'
    };
  }
  
  @Post('extract-frames')
  async extractFrames(@Body() data: { 
    inputPath: string, 
    outputDir?: string, 
    fps?: number 
  }) {
    const { inputPath, fps = 1 } = data;
    
    // If outputDir is not provided, create one based on input filename
    const outputDir = data.outputDir || path.join(
      path.dirname(inputPath),
      `${path.basename(inputPath, path.extname(inputPath))}_frames`
    );
    
    console.log(`Received request to extract frames: ${inputPath} -> ${outputDir} at ${fps} fps`);
    
    try {
      // Extract frames with progress display
      const result = await this.videoProcessorService.extractFrames(
        inputPath,
        outputDir,
        fps
      );
      
      return { 
        success: result,
        input: inputPath,
        outputDir,
        fps,
        message: result ? 'Frame extraction completed successfully' : 'Frame extraction failed'
      };
    } catch (error) {
      return {
        success: false,
        message: `Error: ${error.message}`
      };
    }
  }
  
  @Get('check-output/:outputPath')
  async checkOutput(@Param('outputPath') outputPath: string) {
    // Use the private method through a public wrapper
    const exists = await this.videoProcessorService.checkIfOutputExists(outputPath);
    
    return {
      path: outputPath,
      exists,
      message: exists ? 'Output already exists' : 'Output does not exist'
    };
  }
  
  @Get('check-frames/:directory')
  async checkFrames(@Param('directory') directory: string) {
    const result = await this.videoProcessorService.checkFramesExistInDirectory(directory);
    
    return {
      directory,
      framesExist: result.exists,
      frameCount: result.count,
      message: result.exists 
        ? `Directory contains ${result.count} frame files` 
        : 'No frame files found in directory'
    };
  }
} 