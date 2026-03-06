#!/usr/bin/env node

// MCP Server starter with explicit environment variables
// This ensures env vars are set for auto-documenter

// Set environment variables
process.env.ENABLE_ROTATION = 'true';
process.env.PRIMARY_PROVIDER = 'gemini';
process.env.GEMINI_API_KEY = 'AIzaSyAfduIFUzab5rFe1sMFqyfHjTR-9oSN78o';
process.env.GEMINI_MODEL = 'gemini-2.5-flash-lite';
process.env.GROQ_API_KEY = '';
process.env.GROQ_MODEL = 'llama-3.3-70b-versatile';
process.env.OLLAMA_MODEL = 'gpt-oss:120b-cloud';
process.env.OPENROUTER_API_KEY = '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';

// Import and run the MCP server (ES module)
import('./build/index.js');
