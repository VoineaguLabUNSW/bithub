<script context="module">
    import igv from '../../../node_modules/igv/dist/igv.esm.js';
    let browserContainer = document.createElement('div')
    let browser;
    igv.createBrowser(browserContainer, {genome: 'hg38'}).then(v => browser=v)
</script>

<script>
    import { onMount } from 'svelte'

    export let currentRow;
    export let filteredStore;

    $: {
        if(browser && $filteredStore && $currentRow !== undefined) {
            let [chr, start, end] = [3, 4, 5].map(col_i =>  $filteredStore.columns[col_i][$currentRow]);
            browser.search(`chr${chr}:${start}-${end}`)
        }
    }

    let div;
    onMount(() => div.append(browserContainer));
</script>

<div bind:this={div}></div>