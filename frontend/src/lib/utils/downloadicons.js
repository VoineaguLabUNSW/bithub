/**
 * Font Awesome path data for the Plotly mode-bar download buttons.
 *
 * Extracted here because two components need the same three buttons and the
 * paths are 500-character string literals: inlining them twice guarantees the
 * chat's icons drift from the site's after the first edit. plot.svelte keeps
 * its own copies for now (its buttons are entangled with the sidebar controls);
 * chatfigure.svelte uses these.
 *
 * Sources: fontawesome.com/icons/bezier-curve, /file-image, /file-csv.
 */
const SVG_PATH = 'M368 80h32v32H368V80zM352 32c-17.7 0-32 14.3-32 32H128c0-17.7-14.3-32-32-32H32C14.3 32 0 46.3 0 64v64c0 17.7 14.3 32 32 32V352c-17.7 0-32 14.3-32 32v64c0 17.7 14.3 32 32 32H96c17.7 0 32-14.3 32-32H320c0 17.7 14.3 32 32 32h64c17.7 0 32-14.3 32-32V384c0-17.7-14.3-32-32-32V160c17.7 0 32-14.3 32-32V64c0-17.7-14.3-32-32-32H352zM96 160c17.7 0 32-14.3 32-32H320c0 17.7 14.3 32 32 32V352c-17.7 0-32 14.3-32 32H128c0-17.7-14.3-32-32-32V160zM48 400H80v32H48V400zm320 32V400h32v32H368zM48 112V80H80v32H48z';

const PNG_PATH = 'M64 0C28.7 0 0 28.7 0 64V448c0 35.3 28.7 64 64 64H320c35.3 0 64-28.7 64-64V160H256c-17.7 0-32-14.3-32-32V0H64zM256 0V128H384L256 0zM64 256a32 32 0 1 1 64 0 32 32 0 1 1 -64 0zm152 32c5.3 0 10.2 2.6 13.2 6.9l88 128c3.4 4.9 3.7 11.3 1 16.5s-8.2 8.6-14.2 8.6H216 176 128 80c-5.8 0-11.1-3.1-13.9-8.1s-2.8-11.2 .2-16.1l48-80c2.9-4.8 8.1-7.8 13.7-7.8s10.8 2.9 13.7 7.8l12.8 21.4 48.3-70.2c3-4.3 7.9-6.9 13.2-6.9z';

const CSV_PATH = 'M0 64C0 28.7 28.7 0 64 0H224V128c0 17.7 14.3 32 32 32H384V304H176c-35.3 0-64 28.7-64 64V512H64c-35.3 0-64-28.7-64-64V64zm384 64H256V0L384 128zM200 352h16c22.1 0 40 17.9 40 40v8c0 8.8-7.2 16-16 16s-16-7.2-16-16v-8c0-4.4-3.6-8-8-8H200c-4.4 0-8 3.6-8 8v80c0 4.4 3.6 8 8 8h16c4.4 0 8-3.6 8-8v-8c0-8.8 7.2-16 16-16s16 7.2 16 16v8c0 22.1-17.9 40-40 40H200c-22.1 0-40-17.9-40-40V392c0-22.1 17.9-40 40-40zm133.1 0H368c8.8 0 16 7.2 16 16s-7.2 16-16 16H333.1c-7.2 0-13.1 5.9-13.1 13.1c0 5.2 3 9.9 7.8 12l37.4 16.6c16.3 7.2 26.8 23.4 26.8 41.2c0 24.9-20.2 45.1-45.1 45.1H304c-8.8 0-16-7.2-16-16s7.2-16 16-16h42.9c7.2 0 13.1-5.9 13.1-13.1c0-5.2-3-9.9-7.8-12l-37.4-16.6c-16.3-7.2-26.8-23.4-26.8-41.2c0-24.9 20.2-45.1 45.1-45.1zm98.9 0c8.8 0 16 7.2 16 16v31.6c0 23 5.5 45.6 16 66c10.5-20.3 16-42.9 16-66V368c0-8.8 7.2-16 16-16s16 7.2 16 16v31.6c0 34.7-10.3 68.7-29.6 97.6l-5.1 7.7c-3 4.5-8 7.1-13.3 7.1s-10.3-2.7-13.3-7.1l-5.1-7.7c-19.3-28.9-29.6-62.9-29.6-97.6V368c0-8.8 7.2-16 16-16z';

const toIcon = (path) => ({ path, width: 512, height: 512 });

export const svgIcon = toIcon(SVG_PATH);
export const pngIcon = toIcon(PNG_PATH);
export const csvIcon = toIcon(CSV_PATH);
