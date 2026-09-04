/**
 * Checks renderMarkdown: structure renders, injection does not.
 *
 *   node src/lib/utils/markdown.test.mjs
 *
 * Uses linkedom for a DOM, since the renderer needs document.createElement.
 */
// jsdom, not linkedom: DOMPurify reports isSupported: false against linkedom
// and passes <script> straight through, which would make these tests pass
// vacuously while proving nothing about the sanitiser.
import { JSDOM } from 'jsdom';

const { window } = new JSDOM('<!doctype html><html><body></body></html>');
globalThis.window = window;
globalThis.document = window.document;
globalThis.Node = window.Node;
globalThis.DocumentFragment = window.DocumentFragment;
globalThis.HTMLTemplateElement = window.HTMLTemplateElement;
globalThis.NodeFilter = window.NodeFilter;
globalThis.Element = window.Element;
globalThis.HTMLFormElement = window.HTMLFormElement;

const { renderMarkdown } = await import('./markdown.js');

// A sanitiser that silently is not running would make every injection test
// below pass for the wrong reason.
const DOMPurify = (await import('dompurify')).default;
if (!DOMPurify.isSupported) {
    console.error('FATAL: DOMPurify reports isSupported: false — tests would be vacuous');
    process.exit(1);
}

let failed = 0;
function check(label, condition) {
    if (!condition) failed++;
    console.log(`  ${condition ? 'ok ' : 'BAD'} ${label}`);
}

// ── structure renders ────────────────────────────────────────────────────
const report = renderMarkdown(
    '**SHANK3 is above average in both datasets.**\n\n' +
    '## Developmental pattern\n\nExpression rises from 2.10 to 4.92.\n\n' +
    '## Caveats\n\n- RIN missing for 157 samples\n- Units differ\n'
);
check('h2 headings become real headings', /<h2 class="[^"]*font-semibold/.test(report));
check('no literal ## survives', !report.includes('##'));
check('bold becomes <strong>', /<strong class="[^"]*font-semibold/.test(report));
check('bullets become <ul><li>', /<ul class="[^"]*list-disc/.test(report) && /<li/.test(report));
check('paragraphs styled', /<p class="[^"]*text-sm/.test(report));

const table = renderMarkdown('| A | B |\n|---|---|\n| 1 | 2 |\n');
check('markdown table renders as <table>', /<table class="[^"]*border-collapse/.test(table));
check('no literal pipe separator survives', !table.includes('|---|'));

// ── injection blocked ────────────────────────────────────────────────────
const attacks = [
    ['<script>alert(1)</script>', 'script'],
    ['<img src=x onerror="alert(1)">', 'onerror'],
    ['<iframe src="//evil.test"></iframe>', 'iframe'],
    ['<a href="javascript:alert(1)">x</a>', 'javascript:'],
    ['<style>body{display:none}</style>', 'style'],
    ['<form action="//evil.test"><input name=p></form>', 'form'],
    ['<div onclick="alert(1)">x</div>', 'onclick'],
    ['<svg><animate onbegin="alert(1)"/></svg>', 'onbegin']
];
for (const [payload, needle] of attacks) {
    const out = renderMarkdown(payload).toLowerCase();
    check(`blocked: ${needle}`, !out.includes(needle.toLowerCase()));
}

// Links must survive but be defanged.
const link = renderMarkdown('[PubMed](https://pubmed.ncbi.nlm.nih.gov/123)');
check('safe link kept', link.includes('pubmed.ncbi.nlm.nih.gov'));
check('link gets rel=noopener', /rel="noopener noreferrer"/.test(link));

check('empty input safe', renderMarkdown('') === '' && renderMarkdown(null) === '');

console.log(failed === 0 ? '\nALL MARKDOWN TESTS PASSED' : `\n${failed} FAILED`);
process.exit(failed === 0 ? 0 : 1);
