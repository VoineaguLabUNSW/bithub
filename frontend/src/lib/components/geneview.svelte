<script>
    import { getFilteredStoreGroup } from '../stores/results'
    import MetadataGraph from '../components/metadatagraph.svelte';
    import VarpartGraph from '../components/varpartgraph.svelte'
    import ResultsGraph from '../components/resultgraph.svelte';
    import Genome from '../components/genome.svelte';
    import { derived } from 'svelte/store'
    import {Tabs, TabItem, Popover} from 'flowbite-svelte';
    import TranscriptGraph from '../components/transcriptgraph.svelte';

    export let currentRow;
    export let filteredStore;

    const filteredBulk = getFilteredStoreGroup(filteredStore, 'Gene expression')
    const filteredSingleCell = getFilteredStoreGroup(filteredStore, 'Cell type specific expression')
    const filteredVarpart = getFilteredStoreGroup(filteredStore, '_varpart')
    const filteredTranscript = getFilteredStoreGroup(filteredStore, '_transcripts')

    const geneInfo = derived(filteredStore, $filteredStore => {
        const [ensembl, symbol, description] = [0, 1, 2].map(col_i => $filteredStore.columns[col_i][$currentRow],)
        return { ensembl, symbol, description }
    })
</script>


<style>
    :global(.igv-chromosome-select-widget-container > select) {
        padding-top: 0px;
    }
</style>

<div class='flex justify-between px-8'>
    <div class='flex gap-2 items-center'>
        <div class='text-3xl'>{$geneInfo?.symbol}</div><div>{'(' + $geneInfo?.ensembl + ')'}</div>
    </div>
    <div class='text-lg'>{$geneInfo?.description}</div>
</div>
<hr>

<Tabs contentClass='bg-white mt-0 shadow-lg sm:rounded-lg h-[calc(100vh-270px)]'>
    <TabItem title="Genome Browser">
        <Genome currentRow={currentRow} filteredStore={filteredStore}/>
    </TabItem>
    <TabItem title="Transcript Expression">
        <div class="h-[calc(100vh-270px)]">
            <TranscriptGraph filteredStore={filteredTranscript} heading={$geneInfo?.symbol}/>
        </div>
    </TabItem>
    <TabItem title="Expression Across Datasets">
        <!-- TODO: hardcoded number of px above to give it defined height and force resizes -->
        <div class="h-[calc(100vh-270px)]">
            <ResultsGraph filteredStore={filteredStore} heading={$geneInfo?.symbol + ' Transformed Mean Log2 (Expression)'}/>
        </div>
    </TabItem>
    <TabItem open title="Gene Expression" disabled={$filteredBulk.datasetIndicesResults.length === 0}>
        <div class="h-[calc(100vh-270px)]">
            <MetadataGraph filteredStore={filteredBulk} heading={$geneInfo?.symbol}/>
        </div>
    </TabItem>
    <TabItem title="Drivers of Variation" disabled={$filteredVarpart.datasetIndicesResults.length === 0}>
        <div class="h-[calc(100vh-270px)]">
            <VarpartGraph filteredStore={filteredVarpart} heading={$geneInfo?.symbol}/>
        </div>
    </TabItem>
    <TabItem disabled={$filteredSingleCell.datasetIndicesResults.length === 0}>
        <div slot='title'>
            <span>Single Cell Datasets</span>
            <button id="b3">
                <i class='fas fa-circle-question'/>
                <span class="sr-only">Show information</span>
            </button>
        </div>

        <div class="h-[calc(100vh-270px)]">
            <MetadataGraph filteredStore={filteredSingleCell} heading={$geneInfo?.symbol}/>
        </div>
    </TabItem>
  </Tabs>
  
  <Popover triggeredBy="#b3" class="w-[700px] text-sm font-light text-gray-500 bg-white dark:bg-gray-800 dark:border-gray-600 dark:text-gray-400" placement="bottom-start">
    <div class="p-3 space-y-2">
      <h3 class="font-semibold text-gray-900 dark:text-white">Single Cell Dataset Details</h3>
      <p>This section allows the detailed exploration of the aggregated single-nucleus datasets on BITHub at the gene from each individual dataset. The CPM expression values can be plotted against several metadata attributes, and users are also able to view cell-type specific expression.</p>
      <p>A box plot is generated for categorial metadata and a scatterplot is generated for numerical-based metadata. In the case of numerical variables, a second categorical variable can be selected to color the data points. Users can highlight and select a specific portion of the plot to zoom in, and select or deselect specific metadata annotations by clicking on the legend.</p>
    </div>
</Popover>
