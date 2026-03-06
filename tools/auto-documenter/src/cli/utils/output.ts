/**
 * CLI Output Utilities
 * @module cli/utils/output
 */

/**
 * ANSI color codes for terminal output
 */
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m'
};

/**
 * Check if colors are supported
 */
const supportsColor = process.stdout.isTTY && !process.env.NO_COLOR;

/**
 * Apply color to text if supported
 */
function colorize(text: string, color: keyof typeof colors): string {
  if (!supportsColor) return text;
  return `${colors[color]}${text}${colors.reset}`;
}

/**
 * Output formatter class
 */
export class Output {
  private verbose: boolean;
  private quiet: boolean;

  constructor(verbose: boolean = false, quiet: boolean = false) {
    this.verbose = verbose;
    this.quiet = quiet;
  }

  /**
   * Print success message
   */
  success(message: string): void {
    if (!this.quiet) {
      console.log(colorize('✓', 'green'), message);
    }
  }

  /**
   * Print error message
   */
  error(message: string): void {
    console.error(colorize('✗', 'red'), colorize(message, 'red'));
  }

  /**
   * Print warning message
   */
  warn(message: string): void {
    if (!this.quiet) {
      console.warn(colorize('⚠', 'yellow'), colorize(message, 'yellow'));
    }
  }

  /**
   * Print info message
   */
  info(message: string): void {
    if (!this.quiet) {
      console.log(colorize('ℹ', 'blue'), message);
    }
  }

  /**
   * Print debug message (only in verbose mode)
   */
  debug(message: string): void {
    if (this.verbose) {
      console.log(colorize('⋯', 'dim'), colorize(message, 'dim'));
    }
  }

  /**
   * Print progress message
   */
  progress(current: number, total: number, message: string): void {
    if (!this.quiet) {
      const percent = Math.round((current / total) * 100);
      const bar = this.createProgressBar(percent);
      process.stdout.write(`\r${colorize(bar, 'cyan')} ${percent}% ${message}`);
      if (current === total) {
        process.stdout.write('\n');
      }
    }
  }

  /**
   * Create progress bar string
   */
  private createProgressBar(percent: number): string {
    const width = 20;
    const filled = Math.round(width * (percent / 100));
    const empty = width - filled;
    return `[${'█'.repeat(filled)}${'░'.repeat(empty)}]`;
  }

  /**
   * Print section header
   */
  header(title: string): void {
    if (!this.quiet) {
      console.log();
      console.log(colorize('━'.repeat(50), 'cyan'));
      console.log(colorize(`  ${title}`, 'bright'));
      console.log(colorize('━'.repeat(50), 'cyan'));
    }
  }

  /**
   * Print summary table
   */
  summary(data: Record<string, string | number>): void {
    if (!this.quiet) {
      console.log();
      for (const [key, value] of Object.entries(data)) {
        console.log(`  ${colorize(key + ':', 'dim')} ${value}`);
      }
      console.log();
    }
  }

  /**
   * Print a simple message
   */
  log(message: string): void {
    if (!this.quiet) {
      console.log(message);
    }
  }

  /**
   * Print newline
   */
  newline(): void {
    if (!this.quiet) {
      console.log();
    }
  }
}

/**
 * Default output instance
 */
export const output = new Output();

/**
 * Create output instance with options
 */
export function createOutput(verbose: boolean, quiet: boolean): Output {
  return new Output(verbose, quiet);
}
