/**
 * Render model output as sanitised HTML.
 *
 * The chat previously showed assistant text verbatim, so a structured answer
 * arrived with literal `##` and `|---|---|` on screen. Rendering it means
 * trusting model output enough to put it in innerHTML, so every string goes
 * through DOMPurify with a tag allowlist that has no script, no style, no
 * iframe and no event handlers.
 */
import { marked } from 'marked';
import DOMPurify from 'dompurify';

marked.setOptions({ gfm: true, breaks: false });

// Tailwind has no default typography for raw tags, so headings and lists would
// otherwise render unstyled. Classes are applied post-parse rather than via a
// custom renderer so the mapping stays readable and easy to adjust.
const CLASSES = {
    h1: 'text-base font-semibold text-gray-900 mt-5 mb-2 first:mt-0',
    h2: 'text-[15px] font-semibold text-gray-900 mt-5 mb-2 first:mt-0 pb-1 border-b border-gray-100',
    h3: 'text-sm font-semibold text-gray-800 mt-4 mb-1.5 first:mt-0',
    h4: 'text-sm font-semibold text-gray-700 mt-3 mb-1 first:mt-0',
    p: 'text-sm text-gray-800 leading-relaxed my-2 first:mt-0 last:mb-0',
    ul: 'list-disc pl-5 my-2 space-y-1 text-sm text-gray-800',
    ol: 'list-decimal pl-5 my-2 space-y-1 text-sm text-gray-800',
    li: 'leading-relaxed',
    strong: 'font-semibold text-gray-900',
    em: 'italic',
    code: 'text-[12.5px] font-mono bg-gray-100 text-gray-800 rounded px-1 py-0.5',
    pre: 'bg-gray-50 border border-gray-200 rounded-lg p-3 my-2 overflow-x-auto text-xs',
    blockquote: 'border-l-2 border-primary-200 pl-3 my-2 text-sm text-gray-600 italic',
    hr: 'my-4 border-gray-100',
    a: 'text-primary-600 hover:text-primary-700 underline',
    // A model should not be hand-building tables (the tools return them), but
    // if one slips through it must still be legible rather than raw pipes.
    table: 'w-full text-sm my-3 border-collapse',
    thead: 'border-b border-gray-200',
    th: 'text-left font-medium text-gray-500 text-xs uppercase tracking-wide px-2 py-1.5',
    td: 'px-2 py-1.5 border-b border-gray-100 text-gray-800',
    tbody: ''
};

const ALLOWED_TAGS = [
    'h1', 'h2', 'h3', 'h4', 'p', 'br', 'strong', 'em', 'b', 'i', 'code', 'pre',
    'ul', 'ol', 'li', 'blockquote', 'hr', 'a', 'span',
    'table', 'thead', 'tbody', 'tr', 'th', 'td', 'sub', 'sup'
];

/** Escape for the fallback path — no HTML reaches the DOM if sanitising fails. */
function escapeHtml(text) {
    return String(text)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
}

export function renderMarkdown(text) {
    if (!text) return '';

    // DOMPurify reports isSupported: false when it has no usable DOM (SSR, or
    // an environment where it could not bind to window). Rendering markdown
    // without it would put unsanitised model output into innerHTML, so fail
    // closed to escaped plain text instead.
    if (!DOMPurify.isSupported || typeof DOMPurify.sanitize !== 'function') {
        return `<p class="${CLASSES.p} whitespace-pre-wrap">${escapeHtml(text)}</p>`;
    }

    const dirty = marked.parse(String(text));
    const clean = DOMPurify.sanitize(dirty, {
        ALLOWED_TAGS,
        ALLOWED_ATTR: ['href', 'title', 'class'],
        ALLOW_DATA_ATTR: false,
        // Model output has no business emitting these; drop them outright.
        FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form', 'input']
    });

    // Style after sanitising: anything the allowlist stripped is already gone,
    // so no class can be attached to an element that survived by accident.
    const host = document.createElement('div');
    host.innerHTML = clean;
    for (const [tag, className] of Object.entries(CLASSES)) {
        if (!className) continue;
        for (const el of host.getElementsByTagName(tag)) {
            el.className = className;
        }
    }
    for (const anchor of host.getElementsByTagName('a')) {
        anchor.setAttribute('target', '_blank');
        anchor.setAttribute('rel', 'noopener noreferrer');
    }
    return host.innerHTML;
}
