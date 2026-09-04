<script>
    import { onMount, onDestroy } from 'svelte';
    import Plotly from 'plotly.js-dist-min';
    import { getFilenameFromHeading } from '../utils/plot';
    import { createRowWriter } from '../utils/save';
    import { svgIcon, pngIcon, csvIcon } from '../utils/downloadicons';

    /** Plotly spec from the chat backend: {plotly_data, plotly_layout, caption}. */
    export let figure;

    let container;

    // The site's plot.svelte is not reused here: it expects a `plotlyArgs`
    // store and a `displaySettings` context supplied by the gene-view layout,
    // and carries palette/sidebar controls that do not apply to a chat reply.
    // The three DOWNLOAD buttons are reused, because a figure a researcher
    // cannot take away is not much use in a reply they want to cite. Same
    // filename helper and the same icons as the site (utils/downloadicons.js),
    // so a chat export is named like a gene-view export.
    const EXPORT_WIDTH = 1200;
    const EXPORT_HEIGHT = 700;

    function filename() {
        return getFilenameFromHeading(figure.plotly_layout?.title?.text);
    }

    /**
     * CSV of the plotted values, derived from the traces rather than from a
     * separate payload — what the reader sees is then exactly what they get.
     *
     * One row per point, with the trace name kept: for a stacked composition
     * bar the trace is the cell type and x is the stratum, so the long format
     * is the one that survives every figure type here without a per-type
     * branch. Pie traces carry labels/values instead of x/y.
     */
    function downloadCSV() {
        const csv = createRowWriter(filename() + '.csv', ',');
        csv.write(['series', 'x', 'y']);
        for (const trace of figure.plotly_data || []) {
            const xs = trace.x ?? trace.labels ?? [];
            const ys = trace.y ?? trace.values ?? [];
            const name = trace.name ?? figure.figure_type ?? '';
            if (Array.isArray(ys) && ys.length) {
                ys.forEach((y, i) => csv.write([name, xs[i] ?? i, y]));
            } else if (Array.isArray(xs) && xs.length) {
                // Box/violin traces put the distribution on one axis only.
                xs.forEach((x, i) => csv.write([name, i, x]));
            }
        }
        csv.close();
    }

    const modeBarButtons = [[
        'autoScale2d', 'zoomIn2d', 'zoomOut2d',
        {
            name: 'Download .svg',
            icon: svgIcon,
            click: (gd) => Plotly.downloadImage(gd, {
                filename: filename(), format: 'svg',
                width: EXPORT_WIDTH, height: EXPORT_HEIGHT
            })
        }, {
            name: 'Download .png',
            icon: pngIcon,
            click: (gd) => Plotly.downloadImage(gd, {
                filename: filename(), format: 'png',
                width: EXPORT_WIDTH, height: EXPORT_HEIGHT
            })
        }, {
            name: 'Download .csv',
            icon: csvIcon,
            click: downloadCSV
        }
    ]];

    onMount(() => {
        Plotly.newPlot(container, figure.plotly_data, figure.plotly_layout, {
            // Shown on hover only (see the CSS below) so a reply stays quiet
            // until the reader reaches for the figure.
            displayModeBar: true,
            displaylogo: false,
            modeBarButtons,
            responsive: true
        });
    });

    onDestroy(() => {
        if (container) Plotly.purge(container);
    });
</script>

<div class="chat-figure border border-gray-200 rounded-xl bg-white p-2">
    <div bind:this={container}></div>
    {#if figure.caption}
        <p class="text-xs text-gray-500 px-2 pb-1">{figure.caption}</p>
    {/if}
    {#if figure.statistical_note?.warnings?.length}
        <!-- Same caveat the model is told to state in prose, kept with the
             figure so it travels with a screenshot. -->
        <p class="text-[11px] text-amber-800 bg-amber-50 border border-amber-200
                  rounded-lg px-2.5 py-1.5 mx-2 mb-1.5">
            {figure.statistical_note.text}
        </p>
    {/if}
</div>

<style>
    /* Reveal the mode bar on hover/focus only. Always-on controls over every
       figure in a scrolling transcript compete with the prose; hidden entirely
       means nobody discovers the downloads. */
    .chat-figure :global(.modebar) {
        opacity: 0;
        transition: opacity 150ms ease;
    }
    .chat-figure:hover :global(.modebar),
    .chat-figure:focus-within :global(.modebar) {
        opacity: 1;
    }
</style>
