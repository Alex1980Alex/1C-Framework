/**
 * HTML Renderer - Convert markdown to HTML with styling
 * @module browser/renderer
 */
import { DocFile, DirNode } from './scanner.js';
/**
 * HTML Renderer class
 */
export declare class HtmlRenderer {
    private title;
    constructor(title?: string);
    /**
     * Get CSS styles
     */
    private getStyles;
    /**
     * Render tree navigation
     */
    private renderTree;
    /**
     * Render page layout
     */
    private renderLayout;
    /**
     * Render index page
     */
    renderIndex(files: DocFile[], tree: DirNode, stats: any): string;
    /**
     * Render documentation page
     */
    renderDoc(file: DocFile, markdown: string, tree: DirNode): string;
    /**
     * Render 404 page
     */
    render404(tree: DirNode): string;
    /**
     * Render search results
     */
    renderSearch(query: string, results: DocFile[], tree: DirNode): string;
}
