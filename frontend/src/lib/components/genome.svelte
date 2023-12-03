<script context="module">
    import igv from '../../../node_modules/igv/dist/igv.esm.js';
    import { asyncReadable } from '@square/svelte-store';

    let browserContainer = document.createElement('div')
    let browser =  asyncReadable(undefined, async () => igv.createBrowser(browserContainer, {genome: 'hg38'}))
</script>

<script>
    import { onMount } from 'svelte'

    export let currentRow;
    export let filteredStore;

    $: {
        if($browser && $filteredStore && $currentRow !== undefined) {
            let [chr, start, end] = [3, 4, 5].map(col_i =>  $filteredStore.columns[col_i][$currentRow]);
            $browser.search(`chr${chr}:${start}-${end}`)
        }
    }

    let div;
    onMount(() => div.append(browserContainer));
</script>

<div bind:this={div}></div>