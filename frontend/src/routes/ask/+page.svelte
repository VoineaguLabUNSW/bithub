<script>
    import { tick, onMount, getContext } from 'svelte';
    import { base } from '$app/paths';
    import { Button, Input, Spinner } from 'flowbite-svelte';
    import Logo from '$lib/components/logo.svelte';
    import ChatMessage from '$lib/components/chatmessage.svelte';
    import { messages, pending, datasets, selected, backendError, health,
             loadDatasets, toggleDataset, selectAllDatasets, selectOneDataset,
             ask, reset, exportChat } from '$lib/stores/chat';

    let draft = '';
    let scroller;

    const SUGGESTIONS = [
        'How does SHANK3 expression change across brain development?',
        'What metadata is available in BrainSpan, and how complete is it?',
        'Plot CTNNB1 against numeric age, colour by region, shape by period',
        'Show a heatmap of SHANK3, MECP2 and FOXP2 across age intervals',
        "Does SHANK3's developmental rise replicate across the bulk datasets?"
    ];

    // Drives the all/clear affordance and the header count.
    $: availableCount = $datasets.filter((d) => d.available).length;

    // Does the backend read the same bundle this page plots?
    //
    // The header used to assert "published bundle" from `data_source` alone,
    // but that field only says the backend is reading *a* bundle, not which
    // one — and since BITHUB_SOURCE became settable the two can diverge
    // (the local pipeline/output copy and CloudFront are different pipeline
    // runs). A chat answering from a different bundle than the plot beside it
    // is the one failure a user cannot see, so it is checked rather than
    // claimed. `$metadata.url` is the source directory; the backend reports
    // the metadata.json inside it.
    const { metadata } = getContext('core');
    $: backendDir = $health?.source_url
        ? $health.source_url.slice(0, $health.source_url.lastIndexOf('/'))
        : undefined;
    $: sourceKnown = Boolean(backendDir && $metadata?.url);
    $: sourceAgrees = sourceKnown && backendDir === $metadata.url;

    onMount(loadDatasets);

    async function send(text) {
        const q = (text ?? draft).trim();
        if (!q) return;
        draft = '';
        await ask(q);
        await tick();
        scroller?.scrollTo({ top: scroller.scrollHeight, behavior: 'smooth' });
    }
</script>

<svelte:head><title>Ask BITHub</title></svelte:head>

<div class="flex flex-col h-screen bg-gray-50">

    <!-- Header, matching the standalone page: real BITHub logo (with its
         blinking cursor), service status, dataset chips, and a way back. -->
    <header class="bg-white border-b border-gray-200 shrink-0">
        <div class="max-w-[1100px] mx-auto px-6 py-3 flex items-center gap-4">
            <!-- The logo SVG carries no width/height and scales to its box,
                 so it needs a sized wrapper (same as the home page). The
                 viewBox is 353.4x99.2, so h-8 pairs with w-[114px]. -->
            <a href="{base}/" class="shrink-0 block w-[114px] h-8" aria-label="BITHub home">
                <Logo/>
            </a>

            <div class="border-l border-gray-200 pl-4">
                <div class="font-semibold leading-tight">Ask BITHub</div>
                <div class="text-xs text-gray-500">
                    {#if $backendError}
                        <span class="text-red-600">● backend unreachable</span>
                    {:else if $health}
                        {$datasets.filter((d) => d.available).length} datasets ·
                        {$health.n_genes.toLocaleString()} genes
                        {#if $health.data_source !== 'published_bundle'}
                            <span class="text-gray-400" title="Reading local CSV/parquet
                                  files, not the site's published data">· local files</span>
                        {:else if sourceAgrees}
                            <span class="text-primary-600" title="Verified: the backend is
                                  reading the same bundle this page plots
                                  ({$health.source_url})">· same bundle as this page</span>
                        {:else if sourceKnown}
                            <span class="text-amber-600 font-medium"
                                  title="The chat is reading {$health.source_url} but this page
                                         plots {$metadata.url}/out.hdf5 — different bundles, so
                                         answers may not match the figures beside them.">
                                · ⚠ different bundle</span>
                        {:else}
                            <span class="text-gray-400" title="Reading a published bundle;
                                  source not reported">· published bundle</span>
                        {/if}
                        <span class="text-green-600 ml-1">● connected</span>
                    {:else}
                        connecting…
                    {/if}
                </div>
            </div>

            <!-- Multi-select: two or more datasets switches the backend into
                 cross-dataset comparison on the z-scored scale. -->
            <div class="flex items-center gap-2 ml-4 min-w-0">
                <span class="text-xs text-gray-500 uppercase tracking-wide shrink-0">Datasets</span>
                <div class="flex flex-wrap items-center gap-1.5 min-w-0">
                    {#each $datasets as ds}
                        <button type="button"
                                disabled={!ds.available}
                                title={ds.available
                                    ? `${ds.description} · ${ds.n_samples} samples · ${ds.unit}`
                                    : `${ds.label} is not loaded into the chat service yet`}
                                on:click={() => toggleDataset(ds.id)}
                                class="text-xs px-2.5 py-1 rounded-full border transition
                                       {!ds.available
                                         ? 'border-dashed border-gray-200 text-gray-300 cursor-not-allowed'
                                         : $selected.includes(ds.id)
                                           ? 'border-primary-500 bg-primary-500 text-white shadow-sm'
                                           : 'border-gray-300 text-gray-600 hover:border-primary-400 hover:bg-primary-50'}">
                            {#if $selected.includes(ds.id)}
                                <i class="fas fa-check mr-1 text-[9px]"></i>
                            {/if}{ds.label}
                        </button>
                    {/each}

                    {#if availableCount > 1}
                        <button type="button"
                                on:click={() => ($selected.length === availableCount
                                    ? selectOneDataset($datasets.find((d) => d.available).id)
                                    : selectAllDatasets())}
                                class="text-[11px] text-primary-600 hover:text-primary-700
                                       hover:underline ml-1 shrink-0">
                            {$selected.length === availableCount ? 'clear' : 'all'}
                        </button>
                    {/if}

                    {#if $selected.length > 1}
                        <span class="text-[11px] text-gray-400 ml-1">
                            {$selected.length} selected — answers compare them on the
                            z-scored scale
                        </span>
                    {/if}
                </div>
            </div>

            <div class="ml-auto flex items-center gap-4 shrink-0">
                {#if $messages.length}
                    <button type="button" on:click={exportChat}
                            title="Download the conversation as JSON, including tables, figure specs and tool attribution"
                            class="text-sm text-gray-600 hover:text-primary-700">
                        <i class="fas fa-download mr-1.5"></i>Export
                    </button>
                    <button type="button" on:click={reset}
                            class="text-sm text-gray-600 hover:text-primary-700">
                        <i class="fas fa-rotate-left mr-1.5"></i>New chat
                    </button>
                {/if}
                <a href="{base}/" class="text-sm text-gray-600 hover:text-primary-700">
                    <i class="fas fa-arrow-left mr-1.5"></i>Back to BITHub
                </a>
            </div>
        </div>
    </header>

    <main bind:this={scroller} class="flex-1 overflow-y-auto">
        <div class="max-w-[1100px] mx-auto px-6 py-6 space-y-5">

            {#if $backendError}
                <div class="flex gap-2.5 text-sm bg-amber-50 border border-amber-200
                            rounded-xl px-4 py-3">
                    <i class="fas fa-plug-circle-xmark text-amber-500 mt-0.5"></i>
                    <span class="text-amber-900">{$backendError}</span>
                </div>
            {/if}

            {#if !$messages.length}
                <div class="pt-8">
                    <div class="text-center mb-7">
                        <div class="w-14 h-14 mx-auto rounded-2xl bg-primary-500 text-white
                                    grid place-items-center text-xl mb-4">
                            <i class="fas fa-comment-dots"></i>
                        </div>
                        <h1 class="text-2xl font-semibold">
                            Ask about gene expression in the developing brain
                        </h1>
                        <p class="text-gray-500 mt-2 text-[15px]">
                            {#if availableCount > 1}
                                Answers are grounded in real expression values from
                                {availableCount} BITHub datasets — bulk RNA-seq and
                                single-nucleus, 8 pcw to adult.
                            {:else}
                                Answers are grounded in BrainSpan — bulk RNA-seq from 524
                                post-mortem samples, 8 pcw to ~40 yrs.
                            {/if}
                        </p>
                    </div>

                    <div class="grid sm:grid-cols-2 gap-2.5 max-w-[760px] mx-auto">
                        {#each SUGGESTIONS as s}
                            <button type="button" on:click={() => send(s)}
                                    class="text-left text-sm px-4 py-3 rounded-xl bg-white border
                                           border-gray-200 hover:border-primary-300
                                           hover:bg-primary-50 shadow-sm transition text-gray-700">
                                {s}
                            </button>
                        {/each}
                    </div>

                    <!-- Derived from /api/datasets, never hardcoded: the scope
                         depends on whether the service is reading the published
                         bundle (all eight) or local files (BrainSpan only), and a
                         static caption goes stale the moment that flips. -->
                    <p class="text-center text-xs text-gray-400 mt-6">
                        {#if availableCount > 1}
                            {availableCount} datasets available — select more than one
                            to compare them. Units differ (RPKM, TPM, CPM), so
                            cross-dataset answers use z-scores.
                        {:else if availableCount === 1}
                            {$datasets.find((d) => d.available)?.label} only — the other
                            BITHub datasets are not loaded into this service.
                        {/if}
                    </p>
                </div>
            {/if}

            {#each $messages as message}
                <ChatMessage {message}/>
            {/each}

            {#if $pending}
                <div class="flex items-center gap-2.5 text-sm text-gray-500">
                    <Spinner size="4"/> querying the expression data…
                </div>
            {/if}
        </div>
    </main>

    <footer class="bg-white border-t border-gray-200 shrink-0">
        <div class="max-w-[1100px] mx-auto px-6 py-3">
            <form class="flex gap-2" on:submit|preventDefault={() => send()}>
                <Input bind:value={draft} disabled={$pending}
                       placeholder="Ask about a gene, a covariate, or what is in the data…"
                       class="flex-1"/>
                <Button type="submit" disabled={$pending || !draft.trim()}>
                    <i class="fas fa-paper-plane"></i>
                </Button>
            </form>
            <p class="text-[11px] text-gray-400 mt-2">
                Expression is log<sub>2</sub>(RPKM+1); gene-view plots are z-scored, so
                absolute values differ. Answers can be wrong — check them against the data.
            </p>
        </div>
    </footer>
</div>
