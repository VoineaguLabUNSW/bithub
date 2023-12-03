<script>
    import { getFilteredStoreGroup } from '../stores/results'
    import MetadataGraph from '../components/metadatagraph.svelte';
    import VarpartGraph from '../components/varpartgraph.svelte'
    import ResultsGraph from '../components/resultgraph.svelte';
    import Genome from '../components/genome.svelte';
    import {Tabs, TabItem, Popover} from 'flowbite-svelte';
    import TranscriptGraph from '../components/transcriptgraph.svelte';

    export let currentRow;
    export let filteredStore;

    let filteredBulk = getFilteredStoreGroup(filteredStore, 'Gene expression')
    let filteredSingleCell = getFilteredStoreGroup(filteredStore, 'Cell type specific expression')
    let filteredVarpart = getFilteredStoreGroup(filteredStore, '_varpart')
    let filteredTranscript = getFilteredStoreGroup(filteredStore, '_transcripts')

</script>


<style>
    :global(.igv-chromosome-select-widget-container > select) {
        padding-top: 0px;
    }
</style>

<div class='flex justify-between px-8'>
    <div class='flex gap-2 items-center'>
        <div class='text-3xl'>{$filteredStore.columns[1][$currentRow]}</div><div>{'(' + $filteredStore.columns[0][$currentRow] + ')'}</div>
    </div>
    <div class='text-lg'>{$filteredStore.columns[2][$currentRow]}</div>
</div>
<hr>

<Tabs contentClass='bg-white mt-0 shadow-lg sm:rounded-lg h-[calc(100vh-270px)]'>
    <TabItem open title="Genome Browser">
        <Genome currentRow={currentRow} filteredStore={filteredStore}/>
    </TabItem>
    <TabItem title="Transcript Expression">
        <div class="h-[calc(100vh-270px)]">
            <TranscriptGraph filteredStore={filteredTranscript}/>
        </div>
    </TabItem>
    <TabItem title="Expression Across Datasets">
        <!-- TODO: hardcoded number of px above to give it defined height and force resizes -->
        <div class="h-[calc(100vh-270px)]">
            <ResultsGraph filteredStore={filteredStore}/>
        </div>
    </TabItem>
    <TabItem title="Gene Expression" disabled={$filteredBulk.datasetIndicesResults.length === 0}>
        <div class="h-[calc(100vh-270px)]">
            <MetadataGraph filteredStore={filteredBulk}/>
        </div>
    </TabItem>
    <TabItem title="Drivers of Variation" disabled={$filteredVarpart.datasetIndicesResults.length === 0}>
        <div class="h-[calc(100vh-270px)]">
            <VarpartGraph filteredStore={filteredVarpart}/>
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
            <MetadataGraph filteredStore={filteredSingleCell}/>
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
