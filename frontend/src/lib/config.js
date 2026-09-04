/**
 * Build-time configuration for the Ask BITHub chat.
 *
 * Vite inlines `import.meta.env.*` at build time and leaves undefined vars as
 * undefined rather than failing, which is what this needs:
 *
 *   - `$env/static/public` HARD FAILS the build when a var is unset, so a
 *     clean checkout (and CI) would break.
 *   - `$env/dynamic/public` reads from a SERVER at runtime. adapter-static
 *     has no server, so it resolves to an empty object and the var silently
 *     never takes effect — worse than failing, because the deployed build
 *     would quietly fall back to localhost.
 *
 * Set these in `frontend/.env` (see .env.example). Values are baked into the
 * bundle by `vite build` and cannot change afterwards.
 */

/**
 * Base URL of the FastAPI chat backend.
 *
 * Default is SAME-ORIGIN (empty string -> relative `/api/...` requests),
 * because in every production path the FastAPI process also serves the built
 * site: `demo.sh` on localhost:8000, and `share.sh` behind an ngrok tunnel.
 *
 * Hardcoding `http://localhost:8000` here was wrong for the tunnel — a
 * visitor's browser resolves localhost to THEIR machine, so the chat could
 * never connect, and an https page calling http://localhost is blocked as
 * mixed content regardless.
 *
 * `vite dev` is the one case that is genuinely cross-origin (page on :5173,
 * API on :8000), so it falls back to the absolute localhost URL.
 */
export const CHAT_API =
    import.meta.env.VITE_CHAT_API ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

/** Show the chat entry point in a PRODUCTION build. `vite dev` always shows
 *  it. Keep false for the GitHub Pages deploy — the public site must not
 *  advertise an endpoint that spends Anthropic credits unthrottled. */
export const SHOW_CHAT = import.meta.env.VITE_SHOW_CHAT === 'true';
