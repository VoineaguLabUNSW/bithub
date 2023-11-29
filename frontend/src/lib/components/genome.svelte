<script>
    import igv from '../../../node_modules/igv/dist/igv.esm.js';

    export let currentRow;
    export let filteredStore;

    let browserContainer;
    $: {
        if($filteredStore && $currentRow !== undefined) {
            let [chr, start, end] = [3, 4, 5].map(col_i =>  $filteredStore.columns[col_i][$currentRow]);
            igv.createBrowser(browserContainer, {genome: 'hg38', locus: 'BRCA1'});
        }
    }
</script>

<div bind:this={browserContainer}></div>