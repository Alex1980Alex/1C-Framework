/**
 * HTML Renderer - Convert markdown to HTML with styling
 * @module browser/renderer
 */
/**
 * Simple markdown to HTML converter
 */
function markdownToHtml(markdown) {
    let html = markdown;
    // Escape HTML
    html = html.replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    // Code blocks (must be before inline code)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
        return `<pre><code class="language-${lang || 'plaintext'}">${code.trim()}</code></pre>`;
    });
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Headers
    html = html.replace(/^######\s+(.+)$/gm, '<h6>$1</h6>');
    html = html.replace(/^#####\s+(.+)$/gm, '<h5>$1</h5>');
    html = html.replace(/^####\s+(.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^#\s+(.+)$/gm, '<h1>$1</h1>');
    // Bold and italic
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
    // Lists
    html = html.replace(/^(\s*)-\s+(.+)$/gm, '$1<li>$2</li>');
    html = html.replace(/^(\s*)\d+\.\s+(.+)$/gm, '$1<li>$2</li>');
    // Wrap consecutive <li> in <ul>
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
    // Horizontal rules
    html = html.replace(/^---+$/gm, '<hr>');
    // Blockquotes
    html = html.replace(/^>\s+(.+)$/gm, '<blockquote>$1</blockquote>');
    // Paragraphs (simple approach)
    html = html.replace(/\n\n+/g, '</p><p>');
    html = '<p>' + html + '</p>';
    // Clean up empty paragraphs
    html = html.replace(/<p>\s*<\/p>/g, '');
    html = html.replace(/<p>(<h[1-6]>)/g, '$1');
    html = html.replace(/(<\/h[1-6]>)<\/p>/g, '$1');
    html = html.replace(/<p>(<pre>)/g, '$1');
    html = html.replace(/(<\/pre>)<\/p>/g, '$1');
    html = html.replace(/<p>(<ul>)/g, '$1');
    html = html.replace(/(<\/ul>)<\/p>/g, '$1');
    html = html.replace(/<p>(<hr>)/g, '$1');
    html = html.replace(/(<hr>)<\/p>/g, '$1');
    html = html.replace(/<p>(<blockquote>)/g, '$1');
    html = html.replace(/(<\/blockquote>)<\/p>/g, '$1');
    return html;
}
/**
 * HTML Renderer class
 */
export class HtmlRenderer {
    constructor(title = 'Documentation Browser') {
        this.title = title;
    }
    /**
     * Get CSS styles
     */
    getStyles() {
        return `
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        line-height: 1.6;
        color: #333;
        background: #f5f5f5;
      }
      .container { display: flex; min-height: 100vh; }
      .sidebar {
        width: 280px;
        background: #2c3e50;
        color: #ecf0f1;
        padding: 20px;
        overflow-y: auto;
        position: fixed;
        height: 100vh;
      }
      .sidebar h1 { font-size: 1.2rem; margin-bottom: 20px; color: #3498db; }
      .sidebar input {
        width: 100%;
        padding: 8px 12px;
        border: none;
        border-radius: 4px;
        margin-bottom: 15px;
        background: #34495e;
        color: #fff;
      }
      .sidebar input::placeholder { color: #95a5a6; }
      .tree { list-style: none; }
      .tree li { margin: 4px 0; }
      .tree a {
        color: #bdc3c7;
        text-decoration: none;
        display: block;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.9rem;
      }
      .tree a:hover { background: #34495e; color: #fff; }
      .tree a.active { background: #3498db; color: #fff; }
      .tree .dir { font-weight: bold; color: #f39c12; cursor: pointer; }
      .tree .dir::before { content: '📁 '; }
      .tree .file::before { content: '📄 '; }
      .tree ul { margin-left: 15px; }
      .main {
        margin-left: 280px;
        flex: 1;
        padding: 30px;
        max-width: 900px;
      }
      .content {
        background: #fff;
        padding: 30px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      }
      .content h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-bottom: 20px; }
      .content h2 { color: #34495e; margin-top: 30px; margin-bottom: 15px; }
      .content h3 { color: #7f8c8d; margin-top: 25px; margin-bottom: 10px; }
      .content p { margin-bottom: 15px; }
      .content ul, .content ol { margin-left: 25px; margin-bottom: 15px; }
      .content li { margin-bottom: 5px; }
      .content code {
        background: #f8f9fa;
        padding: 2px 6px;
        border-radius: 3px;
        font-family: 'Fira Code', 'Consolas', monospace;
        font-size: 0.9em;
        color: #e74c3c;
      }
      .content pre {
        background: #2c3e50;
        color: #ecf0f1;
        padding: 15px;
        border-radius: 6px;
        overflow-x: auto;
        margin-bottom: 15px;
      }
      .content pre code { background: none; color: inherit; padding: 0; }
      .content blockquote {
        border-left: 4px solid #3498db;
        padding-left: 15px;
        margin: 15px 0;
        color: #7f8c8d;
      }
      .content hr { border: none; border-top: 1px solid #eee; margin: 25px 0; }
      .content a { color: #3498db; }
      .content a:hover { text-decoration: underline; }
      .meta {
        background: #f8f9fa;
        padding: 10px 15px;
        border-radius: 4px;
        margin-bottom: 20px;
        font-size: 0.85rem;
        color: #7f8c8d;
      }
      .stats { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 20px; }
      .stat {
        background: #fff;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      }
      .stat-value { font-size: 1.5rem; font-weight: bold; color: #3498db; }
      .stat-label { color: #7f8c8d; font-size: 0.85rem; }
      .file-list { list-style: none; }
      .file-list li {
        background: #fff;
        margin: 8px 0;
        padding: 12px 15px;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      }
      .file-list a { text-decoration: none; color: #2c3e50; display: block; }
      .file-list .path { color: #7f8c8d; font-size: 0.85rem; }
      .file-list .type {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 3px;
        font-size: 0.75rem;
        margin-left: 10px;
      }
      .type-documentation { background: #3498db; color: #fff; }
      .type-review { background: #e74c3c; color: #fff; }
      .type-testplan { background: #2ecc71; color: #fff; }
      .type-other { background: #95a5a6; color: #fff; }
    `;
    }
    /**
     * Render tree navigation
     */
    renderTree(node, currentPath = '') {
        if (!node.children || node.children.length === 0) {
            return '';
        }
        let html = '<ul class="tree">';
        for (const child of node.children) {
            if (child.type === 'directory') {
                html += `<li><span class="dir">${child.name}</span>`;
                html += this.renderTree(child, currentPath);
                html += '</li>';
            }
            else {
                const isActive = child.path === currentPath;
                const activeClass = isActive ? ' active' : '';
                html += `<li><a href="/doc/${encodeURIComponent(child.path)}" class="file${activeClass}">${child.name}</a></li>`;
            }
        }
        html += '</ul>';
        return html;
    }
    /**
     * Render page layout
     */
    renderLayout(content, tree, currentPath = '') {
        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${this.title}</title>
  <style>${this.getStyles()}</style>
</head>
<body>
  <div class="container">
    <nav class="sidebar">
      <h1>📚 ${this.title}</h1>
      <input type="text" placeholder="Search..." id="search" onkeyup="filterTree(this.value)">
      <a href="/" style="color: #3498db; display: block; margin-bottom: 15px;">← Back to Index</a>
      ${this.renderTree(tree, currentPath)}
    </nav>
    <main class="main">
      ${content}
    </main>
  </div>
  <script>
    function filterTree(query) {
      const items = document.querySelectorAll('.tree a');
      query = query.toLowerCase();
      items.forEach(item => {
        const text = item.textContent.toLowerCase();
        const li = item.closest('li');
        if (text.includes(query) || !query) {
          li.style.display = '';
        } else {
          li.style.display = 'none';
        }
      });
    }
  </script>
</body>
</html>`;
    }
    /**
     * Render index page
     */
    renderIndex(files, tree, stats) {
        const content = `
      <div class="content">
        <h1>Documentation Index</h1>
        <div class="stats">
          <div class="stat">
            <div class="stat-value">${stats.totalFiles}</div>
            <div class="stat-label">Total Files</div>
          </div>
          <div class="stat">
            <div class="stat-value">${stats.directories}</div>
            <div class="stat-label">Directories</div>
          </div>
          <div class="stat">
            <div class="stat-value">${stats.byType.documentation || 0}</div>
            <div class="stat-label">Documentation</div>
          </div>
          <div class="stat">
            <div class="stat-value">${stats.byType.review || 0}</div>
            <div class="stat-label">Reviews</div>
          </div>
          <div class="stat">
            <div class="stat-value">${stats.byType.testplan || 0}</div>
            <div class="stat-label">Test Plans</div>
          </div>
        </div>
        <h2>Recent Files</h2>
        <ul class="file-list">
          ${files
            .sort((a, b) => b.modified.getTime() - a.modified.getTime())
            .slice(0, 20)
            .map(f => `
              <li>
                <a href="/doc/${encodeURIComponent(f.relativePath)}">
                  <strong>${f.title || f.name}</strong>
                  <span class="type type-${f.type}">${f.type}</span>
                  <div class="path">${f.directory || '/'}</div>
                </a>
              </li>
            `).join('')}
        </ul>
      </div>
    `;
        return this.renderLayout(content, tree);
    }
    /**
     * Render documentation page
     */
    renderDoc(file, markdown, tree) {
        const html = markdownToHtml(markdown);
        const content = `
      <div class="content">
        <div class="meta">
          <strong>Path:</strong> ${file.relativePath} |
          <strong>Type:</strong> ${file.type} |
          <strong>Modified:</strong> ${file.modified.toLocaleDateString()}
        </div>
        ${html}
      </div>
    `;
        return this.renderLayout(content, tree, file.relativePath);
    }
    /**
     * Render 404 page
     */
    render404(tree) {
        const content = `
      <div class="content">
        <h1>404 - Not Found</h1>
        <p>The requested documentation file was not found.</p>
        <p><a href="/">Return to index</a></p>
      </div>
    `;
        return this.renderLayout(content, tree);
    }
    /**
     * Render search results
     */
    renderSearch(query, results, tree) {
        const content = `
      <div class="content">
        <h1>Search Results: "${query}"</h1>
        <p>Found ${results.length} result(s)</p>
        <ul class="file-list">
          ${results.map(f => `
            <li>
              <a href="/doc/${encodeURIComponent(f.relativePath)}">
                <strong>${f.title || f.name}</strong>
                <span class="type type-${f.type}">${f.type}</span>
                <div class="path">${f.directory || '/'}</div>
              </a>
            </li>
          `).join('')}
        </ul>
      </div>
    `;
        return this.renderLayout(content, tree);
    }
}
//# sourceMappingURL=renderer.js.map