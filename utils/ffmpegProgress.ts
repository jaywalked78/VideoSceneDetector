import { spawn } from 'child_process';
import readline from 'readline';

export interface FFmpegProgress {
  frame: number;
  fps: number;
  q: number;
  size: string;
  time: string;
  bitrate: string;
  speed: string;
  progress: number; // Value between 0-100
}

export interface FFmpegProgressOptions {
  duration?: number; // Total duration in seconds (if known)
  onProgress?: (progress: FFmpegProgress) => void;
  onComplete?: () => void;
  onError?: (error: Error) => void;
}

/**
 * Execute FFMPEG command with progress tracking
 * @param ffmpegArgs FFMPEG command arguments
 * @param options Progress tracking options
 * @returns Promise that resolves when process completes
 */
export function executeFFmpegWithProgress(
  ffmpegArgs: string[],
  options: FFmpegProgressOptions = {}
): Promise<void> {
  return new Promise((resolve, reject) => {
    // Add progress output arguments if not already present
    if (!ffmpegArgs.includes('-progress')) {
      ffmpegArgs.push('-progress', 'pipe:1');
    }
    
    // Ensure loglevel is set to get progress info
    const logLevelIndex = ffmpegArgs.indexOf('-loglevel');
    if (logLevelIndex === -1) {
      ffmpegArgs.push('-loglevel', 'error');
    }

    const ffmpeg = spawn('ffmpeg', ffmpegArgs);
    let lastProgress: Partial<FFmpegProgress> = {};
    
    // Parse progress output
    const rl = readline.createInterface({
      input: ffmpeg.stdout,
      terminal: false
    });

    // Add this to ensure we're in unbuffered mode for terminal output
    process.stdout.isTTY = true;
    
    rl.on('line', (line) => {
      const [key, value] = line.split('=');
      if (!key || !value) return;

      switch (key.trim()) {
        case 'frame':
          lastProgress.frame = parseInt(value, 10);
          break;
        case 'fps':
          lastProgress.fps = parseFloat(value);
          break;
        case 'q':
          lastProgress.q = parseFloat(value);
          break;
        case 'size':
          lastProgress.size = value.trim();
          break;
        case 'time':
          lastProgress.time = value.trim();
          // Calculate progress percentage if duration is known
          if (options.duration && value.includes(':')) {
            const timeParts = value.split(':');
            const seconds = 
              parseInt(timeParts[0], 10) * 3600 + 
              parseInt(timeParts[1], 10) * 60 + 
              parseFloat(timeParts[2]);
            lastProgress.progress = Math.min(Math.round((seconds / options.duration) * 100), 100);
          }
          break;
        case 'bitrate':
          lastProgress.bitrate = value.trim();
          break;
        case 'speed':
          lastProgress.speed = value.trim();
          break;
        case 'progress':
          if (value.trim() === 'end') {
            lastProgress.progress = 100;
            if (options.onProgress && lastProgress.frame !== undefined) {
              options.onProgress(lastProgress as FFmpegProgress);
            }
            if (options.onComplete) {
              options.onComplete();
            }
          } else if (options.onProgress && lastProgress.frame !== undefined) {
            // If duration is unknown, make a rougher estimate
            if (lastProgress.progress === undefined) {
              lastProgress.progress = 0; // We can't estimate without duration
            }
            // Call the progress callback without trying to flush
            options.onProgress(lastProgress as FFmpegProgress);
          }
          break;
      }
    });

    // Handle error output
    ffmpeg.stderr.on('data', (data) => {
      console.error(`FFMPEG Error: ${data.toString()}`);
    });

    // Handle process exit
    ffmpeg.on('close', (code) => {
      rl.close();
      if (code === 0) {
        resolve();
      } else {
        const error = new Error(`FFMPEG process exited with code ${code}`);
        if (options.onError) {
          options.onError(error);
        }
        reject(error);
      }
    });

    // Handle process error
    ffmpeg.on('error', (err) => {
      rl.close();
      if (options.onError) {
        options.onError(err);
      }
      reject(err);
    });
  });
}

/**
 * Format progress as a terminal progress bar
 * @param progress The current progress (0-100)
 * @param width Width of progress bar in characters
 * @returns Formatted progress bar string
 */
export function formatProgressBar(progress: number, width = 30): string {
  const filledWidth = Math.round((progress / 100) * width);
  const emptyWidth = width - filledWidth;
  
  const filled = '█'.repeat(filledWidth);
  const empty = '░'.repeat(emptyWidth);
  
  return `[${filled}${empty}] ${progress.toFixed(1)}%`;
}

/**
 * Simple progress logging that doesn't rely on terminal control characters
 */
export function logFFmpegProgress(progress: FFmpegProgress): void {
  const progressBar = formatProgressBar(progress.progress);
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] FFMPEG Progress: ${progress.progress.toFixed(1)}% | FPS: ${progress.fps || 0} | Speed: ${progress.speed || 'N/A'}`);
} 