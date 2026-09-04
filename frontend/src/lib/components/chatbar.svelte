<script>
    /**
     * Proportion bar for part-of-whole results (variance decomposition).
     *
     * A table makes the reader compare numbers themselves; a single bar shows
     * the dominant component at a glance and keeps exact fractions in the
     * legend. Colours come from the backend so a covariate is the same colour
     * in every answer.
     */
    export let bar;

    // Segments under this width get no inline label — it would overflow the
    // segment and collide with its neighbour. The legend still carries them.
    const MIN_LABEL_PERCENT = 8;
</script>

<div class="border border-gray-200 rounded-xl overflow-hidden">
    <div class="px-3.5 py-2 bg-gray-50 border-b border-gray-100">
        <div class="text-[11px] uppercase tracking-wide text-gray-500">
            {bar.title}
        </div>
        {#if bar.subtitle}
            <div class="text-sm font-semibold text-gray-900 mt-0.5">{bar.subtitle}</div>
        {/if}
    </div>

    <div class="px-3.5 py-3">
        <div class="flex h-6 w-full rounded-md overflow-hidden" role="img"
             aria-label={bar.segments.map((s) => `${s.label} ${s.percent}%`).join(', ')}>
            {#each bar.segments as segment}
                <div class="flex items-center justify-center overflow-hidden
                            transition-[flex-grow] duration-300"
                     style="flex: {segment.fraction} 0 0; background-color: {segment.color}"
                     title="{segment.label} — {segment.percent}%">
                    {#if segment.percent >= MIN_LABEL_PERCENT}
                        <span class="text-[10px] font-medium text-white/95 px-1 truncate">
                            {segment.percent}%
                        </span>
                    {/if}
                </div>
            {/each}
        </div>

        <div class="flex flex-wrap gap-x-3 gap-y-1 mt-2.5">
            {#each bar.segments as segment}
                <span class="inline-flex items-center gap-1.5 text-[12px] text-gray-700"
                      title={segment.components
                          ? segment.components.map((c) => `${c.label} ${(c.fraction * 100).toFixed(2)}%`).join(', ')
                          : null}>
                    <span class="w-2.5 h-2.5 rounded-sm shrink-0"
                          style="background-color: {segment.color}"></span>
                    {segment.label}
                    <span class="text-gray-500">{segment.percent}%</span>
                    {#if segment.components}
                        <span class="text-gray-400 text-[11px]">
                            ({segment.components.length})
                        </span>
                    {/if}
                </span>
            {/each}
        </div>

        {#if bar.footnote}
            <div class="text-[11px] text-gray-500 mt-2.5">{bar.footnote}</div>
        {/if}
    </div>
</div>
