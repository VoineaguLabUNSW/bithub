<script context="module">
    import { withoutNullsStr } from '$lib/utils/hdf5.js';
    import igv from '../../../node_modules/igv/dist/igv.esm.js';
    import { asyncReadable } from '@square/svelte-store';

    let browserContainer = document.createElement('div')
    let browser = asyncReadable(undefined, async () => igv.createBrowser(browserContainer, {
        genome: 'hg38', 
        trackDefaults: { annotation: { autoHeight: true, maxHeight: 100}},
        tracks:[{
                name: "Ensembl (release 94)",
                type: "annotation",
                url: "https://s3.amazonaws.com/igv.org.genomes/hg38/Homo_sapiens.GRCh38.94.chr.gff3.gz",
                indexURL: "https://s3.amazonaws.com/igv.org.genomes/hg38/Homo_sapiens.GRCh38.94.chr.gff3.gz.csi",
                displayMode: "EXPANDED",
                color: "purple"
            },{
                name: "Fantom5",
                type: "annotation",
                format: "bigBed",
                url: "https://d33ldq8s2ek4w8.cloudfront.net/bithub/fantom5.bb",
                displayMode: "EXPANDED",
                color: "crimson"
                
            },
        ]
    }))
</script>

<script>
    import { onMount } from 'svelte'

    export let currentRow;
    export let filteredStore;

    $: {
        if($browser && $filteredStore && ($currentRow !== undefined)) {
            let [chr, start, end] = [3, 4, 5].map(col_i =>  $filteredStore.columns[col_i][$currentRow]);
            const locus = `chr${withoutNullsStr(chr)}:${start}-${end}`
            $browser.search(locus)
        }
    }

    let div;
    onMount(() => div.append(browserContainer));
</script>

<div bind:this={div}></div>