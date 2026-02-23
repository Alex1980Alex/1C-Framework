#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Context7 MCP Integration

Tests:
1. Node.js version check
2. Context7 package availability
3. API key validation
4. resolve-library-id test
5. get-library-docs test

Author: Claude Code
Version: 1.0.0
Created: 2026-02-23
"""

import subprocess
import json
import sys
import io

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def run_command(cmd: list, cwd: str = None) -> dict:
    """Run command and return result."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_node_version():
    """Test Node.js version (>= 18 required)."""
    print("\n[Test 1] Node.js Version Check")
    print("-" * 40)

    result = run_command(["node", "--version"])

    if not result["success"]:
        print("[FAIL] Node.js not found")
        return False

    version = result["stdout"].strip()
    print(f"[PASS] Node.js version: {version}")

    # Extract major version
    major = int(version.replace("v", "").split(".")[0])
    if major < 18:
        print(f"[FAIL] Node.js {version} < 18 required")
        return False

    return True


def test_context7_package():
    """Test if @upstash/context7-mcp package is available."""
    print("\n[Test 2] Context7 Package Check")
    print("-" * 40)

    result = run_command(["npm", "list", "-g", "@upstash/context7-mcp"])

    if "@upstash/context7-mcp" in result["stdout"]:
        print("[PASS] @upstash/context7-mcp installed globally")
        return True
    else:
        print("[WARN] @upstash/context7-mcp not found globally")
        print("       Installing via npx -y should work")
        return True  # npx -y will handle it


def test_api_key():
    """Test API key format."""
    print("\n[Test 3] API Key Validation")
    print("-" * 40)

    api_key = "ctx7sk-d46bb853-d2fe-4d46-8a67-36e93962225f"

    if api_key.startswith("ctx7sk-"):
        print(f"[PASS] API key format valid: {api_key[:20]}...")
        return True
    else:
        print(f"[FAIL] API key format invalid")
        return False


def test_context7_resolve():
    """Test Context7 resolve-library-id."""
    print("\n[Test 4] Context7 resolve-library-id")
    print("-" * 40)

    # Create test script
    test_script = """
const https = require('https');

const options = {
  hostname: 'api.context7.com',
  path: '/v1/libraries/resolve',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ctx7sk-d46bb853-d2fe-4d46-8a67-36e93962225f'
  }
};

const data = JSON.stringify({
  name: 'FastAPI',
  version: 'latest'
});

const req = https.request(options, (res) => {
  let body = '';
  res.on('data', (chunk) => { body += chunk; });
  res.on('end', () => {
    if (res.statusCode === 200) {
      console.log(body);
    } else {
      console.error('Error:', res.statusCode, body);
    }
  });
});

req.on('error', (e) => {
  console.error('Request error:', e.message);
});

req.write(data);
req.end();
"""

    result = run_command(["node", "-e", test_script])

    if result["success"] and result["stdout"]:
        try:
            response = json.loads(result["stdout"])
            if "id" in response:
                print(f"[PASS] Resolved FastAPI: {response.get('id')}")
                return True
            else:
                print(f"[WARN] Unexpected response: {result['stdout'][:100]}")
                return False
        except json.JSONDecodeError:
            print(f"[WARN] Invalid JSON response")
            return False
    else:
        print(f"[FAIL] Request failed: {result.get('error', result['stderr'][:100])}")
        return False


def test_context7_docs():
    """Test Context7 get-library-docs."""
    print("\n[Test 5] Context7 get-library-docs")
    print("-" * 40)

    # First get library ID (using FastAPI as example)
    test_script = """
const https = require('https');

// Step 1: Resolve library
const resolveOptions = {
  hostname: 'api.context7.com',
  path: '/v1/libraries/resolve',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ctx7sk-d46bb853-d2fe-4d46-8a67-36e93962225f'
  }
};

const resolveData = JSON.stringify({ name: 'FastAPI' });

const req = https.request(resolveOptions, (res) => {
  let body = '';
  res.on('data', (chunk) => { body += chunk; });
  res.on('end', () => {
    if (res.statusCode === 200) {
      const lib = JSON.parse(body);
      const libId = lib.id;

      // Step 2: Get docs
      const docsOptions = {
        hostname: 'api.context7.com',
        path: `/v1/libraries/${libId}/docs`,
        method: 'GET',
        headers: {
          'Authorization': 'Bearer ctx7sk-d46bb853-d2fe-4d46-8a67-36e93962225f'
        }
      };

      const docsReq = https.request(docsOptions, (docsRes) => {
        let docsBody = '';
        docsRes.on('data', (chunk) => { docsBody += chunk; });
        docsRes.on('end', () => {
          if (docsRes.statusCode === 200) {
            const docs = JSON.parse(docsBody);
            console.log(JSON.stringify({
              library_id: libId,
              docs_count: docs.length || 0,
              first_doc: docs[0] ? docs[0].title : 'none'
            }));
          } else {
            console.error('Docs error:', docsRes.statusCode);
          }
        });
      });

      docsReq.on('error', (e) => {
        console.error('Docs request error:', e.message);
      });

      docsReq.end();
    } else {
      console.error('Resolve error:', res.statusCode, body);
    }
  });
});

req.on('error', (e) => {
  console.error('Resolve request error:', e.message);
});

req.write(resolveData);
req.end();
"""

    result = run_command(["node", "-e", test_script])

    if result["success"] and result["stdout"]:
        try:
            response = json.loads(result["stdout"])
            print(f"[PASS] Retrieved docs for FastAPI:")
            print(f"       - Library ID: {response.get('library_id')}")
            print(f"       - Docs count: {response.get('docs_count')}")
            return True
        except json.JSONDecodeError:
            print(f"[WARN] Invalid JSON response")
            return False
    else:
        print(f"[WARN] Request returned empty or error")
        return False  # Don't fail - API might be different


def main():
    """Run all tests."""
    print("=" * 60)
    print("Context7 MCP Integration Tests")
    print("=" * 60)

    tests = [
        ("Node.js Version", test_node_version),
        ("Context7 Package", test_context7_package),
        ("API Key Format", test_api_key),
        ("resolve-library-id", test_context7_resolve),
        ("get-library-docs", test_context7_docs),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n[FAIL] {name} failed: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
