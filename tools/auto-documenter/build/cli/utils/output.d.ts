/**
 * CLI Output Utilities
 * @module cli/utils/output
 */
/**
 * Output formatter class
 */
export declare class Output {
    private verbose;
    private quiet;
    constructor(verbose?: boolean, quiet?: boolean);
    /**
     * Print success message
     */
    success(message: string): void;
    /**
     * Print error message
     */
    error(message: string): void;
    /**
     * Print warning message
     */
    warn(message: string): void;
    /**
     * Print info message
     */
    info(message: string): void;
    /**
     * Print debug message (only in verbose mode)
     */
    debug(message: string): void;
    /**
     * Print progress message
     */
    progress(current: number, total: number, message: string): void;
    /**
     * Create progress bar string
     */
    private createProgressBar;
    /**
     * Print section header
     */
    header(title: string): void;
    /**
     * Print summary table
     */
    summary(data: Record<string, string | number>): void;
    /**
     * Print a simple message
     */
    log(message: string): void;
    /**
     * Print newline
     */
    newline(): void;
}
/**
 * Default output instance
 */
export declare const output: Output;
/**
 * Create output instance with options
 */
export declare function createOutput(verbose: boolean, quiet: boolean): Output;
