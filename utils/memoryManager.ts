import os from 'os';

export interface MemoryUsage {
  totalMemory: number;
  freeMemory: number;
  usedMemory: number;
  usagePercentage: number;
}

export class MemoryManager {
  private maxUsagePercentage: number;
  private checkIntervalMs: number;
  private intervalId: NodeJS.Timeout | null = null;
  private onHighMemoryCallbacks: Array<() => Promise<void>> = [];

  constructor(maxUsagePercentage = 70, checkIntervalMs = 5000) {
    this.maxUsagePercentage = maxUsagePercentage;
    this.checkIntervalMs = checkIntervalMs;
  }

  /**
   * Get current memory usage statistics
   */
  public getMemoryUsage(): MemoryUsage {
    const totalMemory = os.totalmem();
    const freeMemory = os.freemem();
    const usedMemory = totalMemory - freeMemory;
    const usagePercentage = (usedMemory / totalMemory) * 100;

    return {
      totalMemory,
      freeMemory,
      usedMemory,
      usagePercentage,
    };
  }

  /**
   * Start monitoring memory usage at regular intervals
   */
  public startMonitoring(): void {
    if (this.intervalId) {
      return;
    }

    this.intervalId = setInterval(async () => {
      const { usagePercentage } = this.getMemoryUsage();
      
      if (usagePercentage > this.maxUsagePercentage) {
        console.warn(`High memory usage detected: ${usagePercentage.toFixed(2)}%`);
        await this.executeHighMemoryCallbacks();
      }
    }, this.checkIntervalMs);
  }

  /**
   * Stop monitoring memory usage
   */
  public stopMonitoring(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  /**
   * Register callback to be executed when memory usage exceeds threshold
   */
  public onHighMemory(callback: () => Promise<void>): void {
    this.onHighMemoryCallbacks.push(callback);
  }

  /**
   * Execute all registered high memory callbacks
   */
  private async executeHighMemoryCallbacks(): Promise<void> {
    for (const callback of this.onHighMemoryCallbacks) {
      try {
        await callback();
      } catch (error) {
        console.error('Error in high memory callback:', error);
      }
    }
  }

  /**
   * Check if current operation can proceed based on memory usage
   */
  public canProceed(): boolean {
    const { usagePercentage } = this.getMemoryUsage();
    return usagePercentage <= this.maxUsagePercentage;
  }

  /**
   * Wait until memory usage drops below threshold
   */
  public async waitUntilMemoryAvailable(
    maxWaitTimeMs = 60000,
    checkIntervalMs = 1000
  ): Promise<boolean> {
    const startTime = Date.now();
    
    while (Date.now() - startTime < maxWaitTimeMs) {
      if (this.canProceed()) {
        return true;
      }
      await new Promise(resolve => setTimeout(resolve, checkIntervalMs));
    }
    
    return false;
  }
}

// Export singleton instance for app-wide usage
export const memoryManager = new MemoryManager(); 