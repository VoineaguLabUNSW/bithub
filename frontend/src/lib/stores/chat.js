import { writable, get } from 'svelte/store';
import { CHAT_API } from '$lib/config';

/**
 * Ask BITHub chat state.
 *
 * Module-level stores rather than a context factory: unlike `createCore`,
 * which is instantiated per layout so each page gets its own data handle,
 * the conversation should survive navigation. A user who asks about SHANK3,
 * clicks through to the gene view and comes back should still see the thread.
 *
 * The backend base URL is inlined at build time — see $lib/config for why
 * neither `$env/static/public` nor `$env/dynamic/public` works under
 * adapter-static.
 */
export const API = CHAT_API;

/** @type {import('svelte/store').Writable<Array<Object>>} */
export const messages = writable([]);
export const pending = writable(false);
export const datasets = writable([]);
export const selected = writable([]);
export const backendError = writable(undefined);

/** /api/health payload — drives the "connected" line in the header. */
export const health = writable(undefined);

/**
 * Access key for a shared (e.g. ngrok) instance.
 *
 * Read from the `?k=` query parameter and kept in sessionStorage so the link
 * only has to carry it once. sessionStorage rather than localStorage: it dies
 * with the tab, which suits a key that is shared for a demo and rotated after.
 *
 * This is a shared-secret speed bump for a temporary link, not authentication
 * — anyone with the key can spend credits, and it travels in the URL.
 */
function initialToken() {
    if (typeof window === 'undefined') return '';
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get('k');
    if (fromUrl) {
        sessionStorage.setItem('bithub_chat_key', fromUrl);
        // Drop the key from the address bar so it is not shoulder-surfed or
        // pasted onward by accident — but drop ONLY the key. Rebuilding the
        // URL from pathname alone would also discard ?source=, and a visitor
        // sent a link to a non-default bundle would silently be moved onto
        // the default one.
        params.delete('k');
        const qs = params.toString();
        const clean = window.location.pathname
            + (qs ? `?${qs}` : '')
            + window.location.hash;
        window.history.replaceState({}, '', clean);
        return fromUrl;
    }
    return sessionStorage.getItem('bithub_chat_key') || '';
}

export const accessKey = writable(initialToken());

/** Populate the dataset chips. Safe to call repeatedly; only fetches once. */
let catalogLoaded = false;
export async function loadDatasets() {
    if (catalogLoaded) return;
    try {
        const [dsRes, healthRes] = await Promise.all([
            fetch(`${API}/api/datasets`),
            fetch(`${API}/api/health`)
        ]);
        if (!dsRes.ok) throw new Error(`HTTP ${dsRes.status}`);
        const body = await dsRes.json();
        datasets.set(body.datasets);

        // Preselect the default only. Selecting all eight would make every
        // question a cross-dataset query — each one costs a Range request per
        // dataset, and most questions are about one. The chips make widening
        // the scope a single click.
        const loaded = body.datasets.filter((d) => d.available).map((d) => d.id);
        const fallback = loaded.includes(body.default) ? body.default : loaded[0];
        selected.set(fallback ? [fallback] : []);
        if (healthRes.ok) health.set(await healthRes.json());
        catalogLoaded = true;
        backendError.set(undefined);
    } catch (e) {
        const where = API || (typeof window !== 'undefined' ? window.location.origin : 'this origin');
        backendError.set(
            `Chat backend unreachable at ${where}. ` +
            `If you are running locally, start it with \`./demo.sh\` from the repo root.`
        );
    }
}

/**
 * Select every loaded dataset, or fall back to just the default.
 *
 * Cross-dataset corroboration is the reason remote mode exists, so it should
 * be one click rather than eight.
 */
export function selectAllDatasets() {
    const loaded = get(datasets).filter((d) => d.available).map((d) => d.id);
    selected.set(loaded);
}

export function selectOneDataset(id) {
    selected.set([id]);
}

/** Toggle a dataset chip, refusing to leave the selection empty. */
export function toggleDataset(id) {
    selected.update((list) => {
        const i = list.indexOf(id);
        if (i < 0) return [...list, id];
        return list.length === 1 ? list : list.filter((d) => d !== id);
    });
}

/**
 * Download the conversation as JSON.
 *
 * Everything the backend returned is kept, not just the prose: the tables,
 * figure specs, statistical notes and the tool/dataset attribution per turn.
 * That is the point of exporting from a grounded chat — the numbers are
 * reusable and the provenance is checkable. Plotly specs are included as
 * given, so an exported figure can be re-rendered exactly.
 *
 * Written client-side via a blob rather than through an endpoint: the state
 * already lives in this store and the backend holds no session.
 */
export function exportChat() {
    const turns = get(messages).map((m) => {
        const turn = { role: m.role, content: m.content };
        // Only attach what this turn actually carried, so the file stays
        // readable rather than a wall of empty arrays.
        if (m.datasetsUsed?.length) turn.datasets_used = m.datasetsUsed;
        if (m.toolsUsed?.length) turn.tools_used = m.toolsUsed;
        if (m.datasetsUnavailable?.length) turn.datasets_unavailable = m.datasetsUnavailable;
        if (m.tables?.length) turn.tables = m.tables;
        if (m.figures?.length) turn.figures = m.figures;
        if (m.literature) turn.literature = m.literature;
        if (m.elapsedMs != null) turn.elapsed_ms = m.elapsedMs;
        return turn;
    });

    const payload = {
        source: 'BITHub — Ask BITHub',
        exported_at: new Date().toISOString(),
        datasets_selected: get(selected),
        data_source: get(health)?.data_source,
        n_turns: turns.length,
        conversation: turns
    };

    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    const url = URL.createObjectURL(
        new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = `bithub-chat-${stamp}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

/**
 * Send one turn. History is sent with every request because the backend
 * holds no session state.
 */
export async function ask(text) {
    if (!text.trim() || get(pending)) return;

    const history = get(messages)
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({ role: m.role, content: m.content }));

    messages.update((m) => [...m, { role: 'user', content: text }]);
    pending.set(true);

    try {
        const key = get(accessKey);
        const res = await fetch(`${API}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(key ? { 'X-BITHub-Token': key } : {})
            },
            body: JSON.stringify({ message: text, history, datasets: get(selected) })
        });
        const body = await res.json();
        if (!res.ok) {
            // 401 and 429 carry a human-readable reason from the backend;
            // surfacing the raw status instead would be useless to the user.
            throw new Error(body.detail || `HTTP ${res.status}`);
        }

        messages.update((m) => [...m, {
            role: 'assistant',
            content: body.response,
            figures: body.figures || [],
            tables: body.tables || [],
            literature: body.literature,
            lastGene: body.last_gene,
            datasetsUsed: body.datasets_used || [],
            datasetsUnavailable: body.datasets_unavailable || [],
            toolsUsed: body.tools_used || [],
            elapsedMs: body.elapsed_ms
        }]);
    } catch (e) {
        messages.update((m) => [...m, { role: 'error', content: String(e.message || e) }]);
    } finally {
        pending.set(false);
    }
}

export function reset() {
    messages.set([]);
}
