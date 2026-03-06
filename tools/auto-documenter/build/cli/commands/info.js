/**
 * Info Command - Display system information
 * @module cli/commands/info
 */
import { Command } from 'commander';
import { version, banner } from '../utils/version.js';
import { PROVIDERS, DEFAULT_MODELS, getApiKey } from '../utils/options.js';
import { createOutput } from '../utils/output.js';
/**
 * Check if provider is configured
 */
function checkProviderStatus(provider) {
    if (provider === 'ollama') {
        return { configured: true, reason: 'Local (no API key needed)' };
    }
    const apiKey = getApiKey(provider);
    if (apiKey) {
        return { configured: true, reason: 'API key found' };
    }
    const envVars = {
        gemini: 'GEMINI_API_KEY',
        groq: 'GROQ_API_KEY',
        ollama: '',
        grok: 'XAI_API_KEY',
        openrouter: 'OPENROUTER_API_KEY'
    };
    return { configured: false, reason: `Missing ${envVars[provider]}` };
}
/**
 * Execute info command
 */
function executeInfo(output) {
    console.log(banner);
    output.header('Provider Status');
    for (const provider of PROVIDERS) {
        const status = checkProviderStatus(provider);
        const model = DEFAULT_MODELS[provider];
        const icon = status.configured ? '✓' : '✗';
        const color = status.configured ? '\x1b[32m' : '\x1b[31m';
        const reset = '\x1b[0m';
        console.log(`  ${color}${icon}${reset} ${provider.toUpperCase()}`);
        console.log(`    Model: ${model}`);
        console.log(`    Status: ${status.reason}`);
        console.log();
    }
    output.header('Supported Languages');
    const languages = [
        'TypeScript (.ts, .tsx)',
        'JavaScript (.js, .jsx)',
        'Python (.py)',
        'BSL/1C:Enterprise (.bsl)',
        'Java (.java)',
        'C/C++ (.c, .cpp, .h)',
        'C# (.cs)',
        'Go (.go)',
        'Rust (.rs)',
        'PHP (.php)',
        'Ruby (.rb)'
    ];
    for (const lang of languages) {
        console.log(`  • ${lang}`);
    }
    console.log();
    output.header('Available Commands');
    const commands = [
        { cmd: 'generate <path>', desc: 'Generate documentation.md' },
        { cmd: 'review <path>', desc: 'Generate review.md (code review)' },
        { cmd: 'testplan <path>', desc: 'Generate testplan.md' },
        { cmd: 'inline <path>', desc: 'Generate inline docs (JSDoc/TSDoc)' },
        { cmd: 'info', desc: 'Show this information' }
    ];
    for (const { cmd, desc } of commands) {
        console.log(`  autodoc ${cmd}`);
        console.log(`    ${desc}`);
        console.log();
    }
    output.header('Global Options');
    const options = [
        { opt: '-p, --provider <name>', desc: 'AI provider (gemini, groq, ollama, grok, openrouter)' },
        { opt: '-m, --model <name>', desc: 'Model to use' },
        { opt: '-k, --api-key <key>', desc: 'API key for provider' },
        { opt: '-u, --update', desc: 'Update existing files' },
        { opt: '-r, --recursive', desc: 'Process recursively (default: true)' },
        { opt: '--verbose', desc: 'Verbose output' },
        { opt: '-q, --quiet', desc: 'Quiet mode' }
    ];
    for (const { opt, desc } of options) {
        console.log(`  ${opt}`);
        console.log(`    ${desc}`);
        console.log();
    }
    output.header('Examples');
    const examples = [
        'autodoc generate ./src',
        'autodoc generate ./src -p groq',
        'autodoc review ./src/components --verbose',
        'autodoc testplan ./src/utils -u',
        'autodoc inline ./src -p ollama -m codellama'
    ];
    for (const example of examples) {
        console.log(`  $ ${example}`);
    }
    console.log();
    output.header('Environment Variables');
    const envVars = [
        { name: 'GEMINI_API_KEY', desc: 'Google Gemini API key' },
        { name: 'GROQ_API_KEY', desc: 'Groq API key' },
        { name: 'XAI_API_KEY', desc: 'xAI Grok API key' },
        { name: 'OPENROUTER_API_KEY', desc: 'OpenRouter API key' },
        { name: 'PRIMARY_PROVIDER', desc: 'Default provider' },
        { name: 'ENABLE_ROTATION', desc: 'Enable provider rotation' }
    ];
    for (const { name, desc } of envVars) {
        const value = process.env[name];
        const status = value ? '(set)' : '(not set)';
        console.log(`  ${name} ${status}`);
        console.log(`    ${desc}`);
        console.log();
    }
    console.log(`Version: ${version}`);
    console.log();
}
/**
 * Create info command
 */
export function createInfoCommand() {
    const command = new Command('info')
        .description('Display system information and provider status')
        .action((options, cmd) => {
        const globalOpts = cmd.optsWithGlobals();
        const output = createOutput(globalOpts.verbose, globalOpts.quiet);
        executeInfo(output);
    });
    return command;
}
//# sourceMappingURL=info.js.map