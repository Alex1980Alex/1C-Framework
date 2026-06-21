import Readline from 'readline';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { globSync } from 'glob';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BSL_SOURCE_DIR = process.env.BSL_SOURCE_DIR || path.join(__dirname, '..', '..', 'src', 'projects');
const LOG = (msg) => process.stderr.write(`[bsl-code-search] ${msg}\n`);

// In-memory indexes
const symbolIndex = new Map(); // filePath -> Symbol[]
const callGraph = new Map();   // symbolName -> Caller[]

// --- REGEX-BASED PARSER (tree-sitter-bsl optional) ---

function extractSymbols(content, filePath) {
  const symbols = [];
  const lines = content.split('\n');

  lines.forEach((line, idx) => {
    const m = line.match(/^\s*(Процедура|Функция|Procedure|Function)\s+([\wА-Яа-яЁё]+)\s*\(([^)]*)\)/i);
    if (!m) return;

    const [, typeStr, name, paramsStr] = m;
    const isProcedure = /процедура|procedure/i.test(typeStr);
    const isExport = /Экспорт|Export/i.test(line);
    const paramsCount = paramsStr.trim() ? paramsStr.split(',').length : 0;

    symbols.push({
      name,
      type: isProcedure ? 'procedure' : 'function',
      line: idx + 1,
      is_export: isExport,
      params_count: paramsCount,
    });
  });

  return symbols;
}

function buildCallGraph(filePath, content, symbols) {
  const callPattern = /([\wА-Яа-яЁё]+)\s*\(/g;
  let match;

  while ((match = callPattern.exec(content)) !== null) {
    const calledName = match[1];
    // Skip language keywords
    if (/^(Если|Пока|Для|Возврат|Новый|If|While|For|Return|New)$/i.test(calledName)) continue;

    const callLine = content.substring(0, match.index).split('\n').length;

    // Determine caller (last declared symbol before this position)
    let callerName = '<module>';
    for (const sym of symbols) {
      if (sym.line <= callLine) callerName = sym.name;
    }

    if (!callGraph.has(calledName)) callGraph.set(calledName, []);
    callGraph.get(calledName).push({
      caller_name: callerName,
      caller_file: filePath,
      call_line: callLine,
    });
  }
}

async function indexFiles() {
  LOG(`Scanning ${BSL_SOURCE_DIR} for *.bsl files...`);
  let files;
  try {
    files = globSync(path.join(BSL_SOURCE_DIR, '**/*.bsl').replace(/\\/g, '/'), {
      ignore: ['**/node_modules/**'],
    });
  } catch (e) {
    LOG(`Glob error: ${e.message}`);
    files = [];
  }

  LOG(`Found ${files.length} BSL files`);

  let totalSymbols = 0;
  for (const fp of files) {
    try {
      const content = fs.readFileSync(fp, 'utf-8');
      const symbols = extractSymbols(content, fp);
      if (symbols.length > 0) {
        symbolIndex.set(fp, symbols);
        totalSymbols += symbols.length;
        buildCallGraph(fp, content, symbols);
      }
    } catch (e) {
      // skip unreadable files
    }
  }

  LOG(`Indexed ${symbolIndex.size} files, ${totalSymbols} symbols, ${callGraph.size} call targets`);
}

// --- TOOL IMPLEMENTATIONS ---

function searchSymbols(query, symbolType = 'all', limit = 20) {
  const re = new RegExp(query, 'i');
  const results = [];

  for (const [fp, symbols] of symbolIndex) {
    for (const sym of symbols) {
      if (!re.test(sym.name)) continue;
      if (symbolType !== 'all' && sym.type !== symbolType) continue;
      results.push({ name: sym.name, file_path: fp, line_number: sym.line, is_export: sym.is_export, params_count: sym.params_count, type: sym.type });
      if (results.length >= limit) return results;
    }
  }
  return results;
}

function findCallers(symbolName, limit = 20) {
  const callers = callGraph.get(symbolName) || [];
  return callers.slice(0, limit).map(c => ({
    caller_name: c.caller_name,
    caller_file: c.caller_file,
    call_line: c.call_line,
    context: `${c.caller_name} calls ${symbolName} at line ${c.call_line}`,
  }));
}

function getModuleAst(filePath) {
  // Try exact match first, then search by suffix
  let symbols = symbolIndex.get(filePath);
  if (!symbols) {
    for (const [fp, syms] of symbolIndex) {
      if (fp.endsWith(filePath) || fp.replace(/\\/g, '/').endsWith(filePath.replace(/\\/g, '/'))) {
        symbols = syms;
        filePath = fp;
        break;
      }
    }
  }
  return {
    file_path: filePath,
    symbols_count: symbols ? symbols.length : 0,
    symbols: (symbols || []).map(s => ({ name: s.name, type: s.type, line: s.line, is_export: s.is_export, params_count: s.params_count })),
  };
}

// --- MCP STDIO SERVER ---

const TOOLS = [
  {
    name: 'search_symbols',
    description: 'Search for BSL procedures/functions by name pattern (regex). Returns name, file, line, export status.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Regex pattern to match symbol names' },
        symbol_type: { type: 'string', enum: ['procedure', 'function', 'all'], description: 'Filter by type', default: 'all' },
        limit: { type: 'integer', description: 'Max results', default: 20 },
      },
      required: ['query'],
    },
  },
  {
    name: 'find_callers',
    description: 'Find all callers of a given BSL procedure/function',
    inputSchema: {
      type: 'object',
      properties: {
        symbol_name: { type: 'string', description: 'Exact symbol name to find callers for' },
        limit: { type: 'integer', description: 'Max results', default: 20 },
      },
      required: ['symbol_name'],
    },
  },
  {
    name: 'get_module_ast',
    description: 'Get all procedures/functions in a BSL module file',
    inputSchema: {
      type: 'object',
      properties: {
        file_path: { type: 'string', description: 'Path to BSL file (absolute or suffix match)' },
      },
      required: ['file_path'],
    },
  },
];

function handleRequest(msg) {
  const { id, method, params } = msg;

  if (method === 'initialize') {
    return { jsonrpc: '2.0', id, result: { protocolVersion: '2024-11-05', capabilities: { tools: {} }, serverInfo: { name: 'bsl-code-search', version: '1.0.0' } } };
  }

  if (method === 'tools/list') {
    return { jsonrpc: '2.0', id, result: { tools: TOOLS } };
  }

  if (method === 'tools/call') {
    const { name, arguments: args } = params;
    let result;

    if (name === 'search_symbols') result = searchSymbols(args.query, args.symbol_type || 'all', args.limit || 20);
    else if (name === 'find_callers') result = findCallers(args.symbol_name, args.limit || 20);
    else if (name === 'get_module_ast') result = getModuleAst(args.file_path);
    else return { jsonrpc: '2.0', id, error: { code: -32601, message: `Unknown tool: ${name}` } };

    return { jsonrpc: '2.0', id, result: { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] } };
  }

  if (method && method.startsWith('notifications/')) return null; // ignore notifications

  return { jsonrpc: '2.0', id, error: { code: -32601, message: `Unknown method: ${method}` } };
}

async function main() {
  await indexFiles();
  LOG('MCP server ready (stdio)');

  const rl = Readline.createInterface({ input: process.stdin });
  rl.on('line', (line) => {
    if (!line.trim()) return;
    try {
      const msg = JSON.parse(line);
      const resp = handleRequest(msg);
      if (resp) process.stdout.write(JSON.stringify(resp) + '\n');
    } catch (e) {
      process.stdout.write(JSON.stringify({ jsonrpc: '2.0', error: { code: -32700, message: 'Parse error' } }) + '\n');
    }
  });
  rl.on('close', () => process.exit(0));
}

main().catch(e => { LOG(`Fatal: ${e.message}`); process.exit(1); });
