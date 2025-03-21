declare module 'get-video-duration' {
  export function getVideoDurationInSeconds(filePath: string): Promise<number>;
} 