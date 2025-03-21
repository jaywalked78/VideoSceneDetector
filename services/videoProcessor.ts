/// <reference path="../types/get-video-duration.d.ts" />
import { Injectable, Logger } from '@nestjs/common';
import { memoryManager } from '../utils/memoryManager';
import { executeFFmpegWithProgress, formatProgressBar, logFFmpegProgress } from '../utils/ffmpegProgress';
import { getVideoDurationInSeconds } from 'get-video-duration';
import * as fs from 'fs';
import * as path from 'path';
import axios from 'axios';

@Injectable()
export class VideoProcessorService {
  private readonly logger = new Logger(VideoProcessorService.name);
  private isProcessing = false;
  private processingQueue: Array<{
    type: 'video' | 'frames';
    inputPath: string;
    outputPath: string;
    fps?: number;
    resolve: (result: boolean) => void;
    reject: (error: Error) => void;
  }> = [];
  private webhookUrl: string;
  
  constructor() {
    // Start memory monitoring
    memoryManager.startMonitoring();
    
    // Register high memory callback to pause processing queue
    memoryManager.onHighMemory(async () => {
      this.logger.warn('High memory usage detected, pausing video processing queue');
      await this.pauseProcessingQueue();
    });
    
    // Log that service is ready for processing with progress display
    console.log('Video processor service initialized with progress display capability');
    
    // Get webhook URL from environment variables
    this.webhookUrl = process.env.WEBHOOK_URL || '';
    
    if (this.webhookUrl) {
      this.logger.log(`Webhook notifications configured: ${this.webhookUrl}`);
    } else {
      this.logger.warn('No webhook URL configured. Set WEBHOOK_URL environment variable to enable notifications.');
    }
    
    // Start the queue processor
    this.processQueue();
  }
  
  /**
   * Check if FFMPEG is currently processing a task
   * @returns Whether FFMPEG is busy
   */
  public isBusy(): boolean {
    return this.isProcessing;
  }
  
  /**
   * Get current queue status
   * @returns Queue information
   */
  public getQueueStatus(): {
    busy: boolean;
    queueLength: number;
    currentTask?: string;
  } {
    return {
      busy: this.isProcessing,
      queueLength: this.processingQueue.length,
      currentTask: this.isProcessing ? 'Processing in progress' : undefined
    };
  }
  
  /**
   * Process a video with queue management
   * @param inputPath Input video path
   * @param outputPath Output video path
   * @returns Promise resolving to success status
   */
  async processVideo(inputPath: string, outputPath: string): Promise<boolean> {
    // Create a promise that will resolve when task is complete
    return new Promise((resolve, reject) => {
      // Add task to queue
      this.processingQueue.push({
        type: 'video',
        inputPath,
        outputPath,
        resolve,
        reject
      });
      
      console.log(`📝 Added video processing task to queue: ${inputPath} -> ${outputPath}`);
      console.log(`📊 Current queue length: ${this.processingQueue.length}`);
      
      // Start queue processing (if not already running)
      this.processQueue();
    });
  }
  
  /**
   * Extract frames with queue management
   * @param inputPath Input video path
   * @param outputDir Output directory
   * @param fps Frames per second
   * @returns Promise resolving to success status
   */
  async extractFrames(inputPath: string, outputDir: string, fps: number = 1): Promise<boolean> {
    // Create a promise that will resolve when task is complete
    return new Promise((resolve, reject) => {
      // Add task to queue
      this.processingQueue.push({
        type: 'frames',
        inputPath,
        outputPath: outputDir,
        fps,
        resolve,
        reject
      });
      
      console.log(`📝 Added frame extraction task to queue: ${inputPath} -> ${outputDir} (${fps} fps)`);
      console.log(`📊 Current queue length: ${this.processingQueue.length}`);
      
      // Start queue processing (if not already running)
      this.processQueue();
    });
  }
  
  /**
   * Process the queue, executing one task at a time
   */
  private async processQueue(): Promise<void> {
    // If already processing or queue is empty, do nothing
    if (this.isProcessing || this.processingQueue.length === 0) {
      return;
    }
    
    // Set processing flag to prevent multiple simultaneous tasks
    this.isProcessing = true;
    
    // Get the next task from the queue
    const task = this.processingQueue.shift();
    
    // Add null check to prevent TypeScript errors
    if (!task) {
      this.isProcessing = false;
      return;
    }
    
    console.log('\n' + '='.repeat(80));
    console.log(`🔄 PROCESSING QUEUE: Starting next task (${this.processingQueue.length} remaining in queue)`);
    
    try {
      let result: boolean;
      
      // Process task based on type
      if (task.type === 'video') {
        console.log(`🎬 Starting video processing task: ${task.inputPath} -> ${task.outputPath}`);
        result = await this.processVideoInternal(task.inputPath, task.outputPath);
      } else {
        console.log(`🎞️ Starting frame extraction task: ${task.inputPath} -> ${task.outputPath} (${task.fps} fps)`);
        result = await this.extractFramesInternal(task.inputPath, task.outputPath, task.fps);
      }
      
      // Resolve the task promise
      task.resolve(result);
    } catch (error) {
      console.error(`❌ Error processing queue task: ${error.message}`);
      // Reject the task promise
      task.reject(error);
    } finally {
      // Clear processing flag
      this.isProcessing = false;
      
      console.log(`🔄 QUEUE: Task completed. ${this.processingQueue.length} tasks remaining.`);
      console.log('='.repeat(80) + '\n');
      
      // Process the next task in queue (if any)
      if (this.processingQueue.length > 0) {
        console.log(`⏱️ Starting next task in 1 second...`);
        setTimeout(() => this.processQueue(), 1000); // Small delay between tasks
      } else {
        console.log(`✅ Queue is now empty. System idle.`);
      }
    }
  }
  
  /**
   * Internal method to process video (used by queue processor)
   */
  private async processVideoInternal(inputPath: string, outputPath: string): Promise<boolean> {
    try {
      console.log('\n' + '='.repeat(80));
      console.log(`🎯 STARTING VIDEO PROCESSING TASK`);
      console.log(`📂 Input: ${inputPath}`);
      console.log(`📂 Output: ${outputPath}`);
      console.log('='.repeat(80));

      // Create output directory if needed
      const outputDir = path.dirname(outputPath);
      if (!fs.existsSync(outputDir)) {
        console.log(`📁 Creating output directory: ${outputDir}`);
        fs.mkdirSync(outputDir, { recursive: true });
      }

      // Check if output already exists
      if (this.checkOutputExists(outputPath)) {
        console.log(`⏩ Output already exists, skipping processing`);
        console.log(`🔄 Sending webhook for existing output instead of processing...`);
        
        // Send webhook notification for existing output
        await this.sendWebhookNotification(inputPath, outputPath, true, true);
        
        console.log(`✅ Process complete - used existing output`);
        console.log('='.repeat(80) + '\n');
        return true;
      }
      
      console.log(`🔍 No existing output found at ${outputPath}, proceeding with processing`);
      
      // Memory usage check
      const initialMemory = memoryManager.getMemoryUsage();
      console.log(`💾 Initial memory usage: ${initialMemory.usagePercentage.toFixed(2)}%`);
      
      // Wait if memory usage is too high
      if (!await memoryManager.waitUntilMemoryAvailable()) {
        console.log(`⛔ Memory usage too high for too long, aborting`);
        
        // Send webhook notification for failure due to memory constraints
        await this.sendWebhookNotification(inputPath, outputPath, false);
        
        return false;
      }
      
      // Get video duration for progress calculation
      console.log(`⏱️ Getting video duration...`);
      const duration = await getVideoDurationInSeconds(inputPath);
      
      // Add visual separator for better terminal display
      console.log('\n' + '-'.repeat(80));
      console.log(`📹 PROCESSING VIDEO: ${inputPath} -> ${outputPath}`);
      console.log(`📏 Duration: ${duration.toFixed(2)} seconds`);
      console.log('-'.repeat(80));
      
      // Example FFMPEG command
      const ffmpegArgs = [
        '-i', inputPath,
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-c:a', 'aac',
        outputPath
      ];
      
      // Use terminal-mode progress if stdout is a TTY, otherwise use logging
      const useTerminalProgress = process.stdout.isTTY;
      
      if (useTerminalProgress) {
        console.log('🚀 Progress display enabled (terminal mode)');
      } else {
        console.log('🚀 Progress display enabled (log mode)');
      }
      
      const startTime = Date.now();
      
      // Execute with progress tracking
      await executeFFmpegWithProgress(ffmpegArgs, {
        duration,
        onProgress: (progress) => {
          if (useTerminalProgress) {
            // Terminal mode with progress bar
            process.stdout.write('\r\x1b[K');
            process.stdout.write(
              `${formatProgressBar(progress.progress)} | FPS: ${progress.fps || 0} | Speed: ${progress.speed || 'N/A'}`
            );
          } else {
            // Log mode with timestamps
            logFFmpegProgress(progress);
          }
        },
        onComplete: () => {
          if (useTerminalProgress) {
            process.stdout.write('\n');
          }
          const processingTime = ((Date.now() - startTime) / 1000).toFixed(2);
          console.log('-'.repeat(80));
          console.log(`✅ Video processing complete: ${outputPath}`);
          console.log(`⏱️ Processing time: ${processingTime} seconds`);
          console.log('-'.repeat(80) + '\n');
        },
        onError: (error) => {
          console.log('-'.repeat(80));
          console.log(`❌ Error during video processing: ${error.message}`);
          console.log('-'.repeat(80) + '\n');
        }
      });
      
      // Final memory usage check
      const finalMemory = memoryManager.getMemoryUsage();
      console.log(`💾 Final memory usage: ${finalMemory.usagePercentage.toFixed(2)}%`);
      
      console.log(`🔄 Preparing to send webhook notification...`);
      
      // After successful processing, send webhook notification
      await this.sendWebhookNotification(inputPath, outputPath, true);
      
      return true;
    } catch (error) {
      this.logger.error(`Failed to process video: ${error.message}`);
      console.log(`❌ ERROR: ${error.message}`);
      
      // Send webhook notification for failure
      await this.sendWebhookNotification(inputPath, outputPath, false);
      
      return false;
    } finally {
      console.log(`🏁 Video processing task completed`);
      console.log('='.repeat(80) + '\n');
    }
  }
  
  /**
   * Internal method to extract frames (used by queue processor)
   */
  private async extractFramesInternal(inputPath: string, outputDir: string, fps: number = 1): Promise<boolean> {
    try {
      console.log('\n' + '='.repeat(80));
      console.log(`🎯 STARTING FRAME EXTRACTION TASK`);
      console.log(`📂 Input: ${inputPath}`);
      console.log(`📂 Output directory: ${outputDir}`);
      console.log(`⚙️ FPS: ${fps}`);
      console.log('='.repeat(80));
      
      // Create the output directory if it doesn't exist
      if (!fs.existsSync(outputDir)) {
        console.log(`📁 Creating output directory: ${outputDir}`);
        fs.mkdirSync(outputDir, { recursive: true });
      }
      
      // Check specifically for existing frame files in the directory
      if (this.checkFramesExist(outputDir)) {
        console.log(`⏩ Frame files already exist in ${outputDir}, skipping extraction`);
        console.log(`🔄 Sending webhook for existing frames instead of processing...`);
        
        // Send webhook notification for existing frames
        await this.sendWebhookNotification(inputPath, outputDir, true, true);
        
        console.log(`✅ Process complete - used existing frames`);
        console.log('='.repeat(80) + '\n');
        return true;
      }
      
      console.log(`🔍 No existing frame files found in ${outputDir}, proceeding with extraction`);
      
      // Wait if memory usage is too high
      if (!await memoryManager.waitUntilMemoryAvailable()) {
        this.logger.error('Cannot extract frames - memory usage too high for too long');
        console.log(`⛔ Memory usage too high for too long, aborting frame extraction`);
        
        // Send webhook notification for failure
        await this.sendWebhookNotification(inputPath, outputDir, false);
        
        console.log(`❌ Process failed - memory constraints`);
        console.log('='.repeat(80) + '\n');
        return false;
      }
      
      // Get video duration for progress calculation
      console.log(`⏱️ Getting video duration...`);
      const duration = await getVideoDurationInSeconds(inputPath);
      
      // Add visual separator for better terminal display
      console.log('\n' + '-'.repeat(80));
      console.log(`🎞️ EXTRACTING FRAMES: ${inputPath} -> ${outputDir} (${fps} fps)`);
      console.log(`📏 Duration: ${duration.toFixed(2)} seconds`);
      console.log('-'.repeat(80));
      
      // Define frame pattern
      const framePattern = path.join(outputDir, 'frame_%04d.jpg');
      console.log(`🖼️ Frame filename pattern: ${framePattern}`);
      
      // FFMPEG command for frame extraction
      const ffmpegArgs = [
        '-i', inputPath,
        '-vf', `fps=${fps}`,
        '-q:v', '2', // High quality JPEG
        framePattern
      ];
      
      // Use terminal-mode progress if stdout is a TTY, otherwise use logging
      const useTerminalProgress = process.stdout.isTTY;
      
      if (useTerminalProgress) {
        console.log('🚀 Progress display enabled (terminal mode)');
      } else {
        console.log('🚀 Progress display enabled (log mode)');
      }
      
      const startTime = Date.now();
      
      // Execute with progress tracking
      await executeFFmpegWithProgress(ffmpegArgs, {
        duration,
        onProgress: (progress) => {
          if (useTerminalProgress) {
            // Terminal mode with progress bar
            process.stdout.write('\r\x1b[K');
            process.stdout.write(
              `${formatProgressBar(progress.progress)} | FPS: ${progress.fps || 0} | Speed: ${progress.speed || 'N/A'}`
            );
          } else {
            // Log mode with timestamps
            logFFmpegProgress(progress);
          }
        },
        onComplete: () => {
          if (useTerminalProgress) {
            process.stdout.write('\n');
          }
          const processingTime = ((Date.now() - startTime) / 1000).toFixed(2);
          console.log('-'.repeat(80));
          console.log(`✅ Frame extraction complete: ${outputDir}`);
          console.log(`⏱️ Processing time: ${processingTime} seconds`);
          console.log('-'.repeat(80) + '\n');
        },
        onError: (error) => {
          console.log('-'.repeat(80));
          console.log(`❌ Error during frame extraction: ${error.message}`);
          console.log('-'.repeat(80) + '\n');
        }
      });
      
      // Verify frames were created
      const frameCount = this.countFramesInDirectory(outputDir);
      console.log(`📊 Extracted ${frameCount} frames to ${outputDir}`);
      
      console.log(`🔄 Preparing to send webhook notification...`);
      
      // Send webhook notification
      await this.sendWebhookNotification(inputPath, outputDir, true);
      
      console.log(`✅ Process complete - extracted ${frameCount} frames`);
      console.log('='.repeat(80) + '\n');
      return true;
    } catch (error) {
      this.logger.error(`Failed to extract frames: ${error.message}`);
      console.log(`❌ ERROR during frame extraction: ${error.message}`);
      
      // Send webhook notification for failure
      await this.sendWebhookNotification(inputPath, outputDir, false);
      
      console.log(`❌ Process failed - error during extraction`);
      console.log('='.repeat(80) + '\n');
      return false;
    }
  }
  
  /**
   * Pause the processing queue (used for high memory situations)
   */
  private async pauseProcessingQueue(): Promise<void> {
    // Currently we just wait for memory to free up
    // In the future, this could be expanded to implement a more sophisticated
    // queueing system with priority, cancellation, etc.
    this.logger.log('Processing queue paused');
  }
  
  /**
   * Checks if the output file or frames already exist
   * @param outputPath Path to check for existing output
   * @returns true if output exists, false otherwise
   */
  private checkOutputExists(outputPath: string): boolean {
    // Check for direct file existence
    if (fs.existsSync(outputPath)) {
      this.logger.log(`Output file already exists: ${outputPath}`);
      return true;
    }
    
    // Check for frame directory if this is a frame extraction process
    // Assuming frames are stored in a directory with the same name as the output file without extension
    const outputDir = path.join(
      path.dirname(outputPath),
      path.basename(outputPath, path.extname(outputPath))
    );
    
    if (fs.existsSync(outputDir) && fs.statSync(outputDir).isDirectory()) {
      // Check if directory has frame files (assuming jpg/png frames)
      try {
        const files = fs.readdirSync(outputDir);
        const frameFiles = files.filter(file => 
          file.match(/\.(jpg|jpeg|png)$/i)
        );
        
        if (frameFiles.length > 0) {
          this.logger.log(`Output frames already exist in directory: ${outputDir} (${frameFiles.length} frames)`);
          return true;
        }
      } catch (error) {
        this.logger.error(`Error checking frame directory: ${error.message}`);
      }
    }
    
    return false;
  }
  
  /**
   * Send webhook notification about processing completion
   * @param inputPath Original input file path
   * @param outputPath Output file or directory path
   * @param status Success status
   * @param isExisting Whether this is for existing files
   */
  private async sendWebhookNotification(
    inputPath: string, 
    outputPath: string, 
    status: boolean,
    isExisting: boolean = false
  ): Promise<void> {
    if (!this.webhookUrl) {
      console.log('⚠️ No webhook URL configured. Skipping notification.');
      return;
    }
    
    try {
      const payload = {
        input: inputPath,
        output: outputPath,
        success: status,
        timestamp: new Date().toISOString(),
        existing: isExisting,
        message: isExisting ? 'Output already existed, skipped processing' : 'Processing completed'
      };
      
      // Enhanced terminal output for better debugging
      console.log('\n' + '-'.repeat(80));
      console.log(`📤 SENDING WEBHOOK NOTIFICATION TO: ${this.webhookUrl}`);
      console.log(`📋 Payload: ${JSON.stringify(payload, null, 2)}`);
      
      // Track timing for webhook request
      const startTime = Date.now();
      
      const response = await axios.post(this.webhookUrl, payload, {
        headers: {
          'Content-Type': 'application/json'
        },
        // Add timeout to prevent hanging
        timeout: 10000
      });
      
      const duration = Date.now() - startTime;
      
      // Show detailed webhook response information
      console.log(`✅ WEBHOOK NOTIFICATION SENT SUCCESSFULLY TO n8n webhook`);
      console.log(`⏱️ Response time: ${duration}ms`);
      console.log(`📊 Status: ${response.status} ${response.statusText}`);
      
      if (response.data) {
        console.log(`📡 Response data: ${JSON.stringify(response.data, null, 2)}`);
      }
      
      console.log('-'.repeat(80) + '\n');
      
      this.logger.log(`Webhook notification sent to n8n webhook, status: ${response.status}`);
    } catch (error) {
      console.log('\n' + '-'.repeat(80));
      console.log(`❌ FAILED TO SEND WEBHOOK NOTIFICATION TO: ${this.webhookUrl}`);
      console.log(`🔴 Error: ${error.message}`);
      
      // Show more detailed error information if available
      if (error.response) {
        console.log(`📡 Response status: ${error.response.status}`);
        console.log(`📡 Response data: ${JSON.stringify(error.response.data, null, 2)}`);
      }
      
      console.log('-'.repeat(80) + '\n');
      
      this.logger.error(`Failed to send webhook notification: ${error.message}`);
    }
  }
  
  /**
   * Specifically checks if a directory already contains frame files
   * @param outputDir Directory to check for existing frames
   * @returns true if frame files exist, false otherwise
   */
  private checkFramesExist(outputDir: string): boolean {
    // Check if directory exists
    if (!fs.existsSync(outputDir) || !fs.statSync(outputDir).isDirectory()) {
      return false;
    }
    
    try {
      // Read directory contents
      const files = fs.readdirSync(outputDir);
      
      // Check for files with "frame" in the name
      const frameFiles = files.filter(file => 
        file.toLowerCase().includes('frame') && 
        file.match(/\.(jpg|jpeg|png)$/i)
      );
      
      if (frameFiles.length > 0) {
        this.logger.log(`Found ${frameFiles.length} existing frame files in ${outputDir}`);
        console.log(`🔍 Found ${frameFiles.length} existing frame files in directory`);
        console.log(`📁 First few frames: ${frameFiles.slice(0, 3).join(', ')}${frameFiles.length > 3 ? '...' : ''}`);
        return true;
      }
      
      return false;
    } catch (error) {
      this.logger.error(`Error checking for frame files: ${error.message}`);
      return false;
    }
  }
  
  /**
   * Count frame files in a directory
   * @param directory Directory to check
   * @returns Number of frame files
   */
  private countFramesInDirectory(directory: string): number {
    try {
      if (!fs.existsSync(directory) || !fs.statSync(directory).isDirectory()) {
        return 0;
      }
      
      const files = fs.readdirSync(directory);
      const frameFiles = files.filter(file => 
        file.toLowerCase().includes('frame') && 
        file.match(/\.(jpg|jpeg|png)$/i)
      );
      
      return frameFiles.length;
    } catch (error) {
      this.logger.error(`Error counting frames: ${error.message}`);
      return 0;
    }
  }
  
  /**
   * Public wrapper to check if output exists
   * @param outputPath Path to check
   * @returns Whether output exists
   */
  async checkIfOutputExists(outputPath: string): Promise<boolean> {
    return this.checkOutputExists(outputPath);
  }
  
  /**
   * Public method to check if frames exist in a directory
   * @param directory Directory to check
   * @returns Whether frames exist and frame count
   */
  async checkFramesExistInDirectory(directory: string): Promise<{exists: boolean, count: number}> {
    const exists = this.checkFramesExist(directory);
    const count = exists ? this.countFramesInDirectory(directory) : 0;
    
    return {
      exists,
      count
    };
  }
} 