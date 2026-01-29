<script>
    import { getFilteredStoreGroup } from '../stores/results'
    import MetadataGraph from '../components/metadatagraph.svelte';
    import VarpartGraph from '../components/varpartgraph.svelte'
    import ResultsGraph from '../components/resultgraph.svelte';
    import Genome from '../components/genome.svelte';
    import { derived } from 'svelte/store'
    import { Tabs, TabItem, Popover } from 'flowbite-svelte';
    import TranscriptGraph from '../components/transcriptgraph.svelte';
    import { withoutNullsStr } from '../utils/hdf5'

    export let currentRow;
    export let filteredStore;

    const filteredBulk = getFilteredStoreGroup(filteredStore, ['Bulk', '_custom'])
    const filteredSingleCell = getFilteredStoreGroup(filteredStore, ['SingleCell'])
    const filteredVarpart = getFilteredStoreGroup(filteredStore, ['_varpart'])
    const filteredTranscript = getFilteredStoreGroup(filteredStore, ['_transcripts'])

    const geneInfo = derived(filteredStore, $filteredStore => {
        const [ensembl, symbol, description] = [0, 1, 2].map(col_i => withoutNullsStr($filteredStore.columns[col_i][$currentRow]))
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
    <TabItem open>
        <div slot='title'>
            <span>Gene Exp Across Datasets</span>
            <button id="exp-help">
                <i class='fas fa-circle-question'/>
                <span class="sr-only">Show information</span>
            </button>
        </div>
        <!-- TODO: hardcoded number of px above to give it defined height and force resizes -->
        <div class="h-[calc(100vh-270px)]">
            <ResultsGraph filteredStore={filteredStore} heading={$geneInfo?.symbol + ' - Z-Score Transformed Mean Log2 (Expression)'}/>
        </div>
    </TabItem>
    <TabItem disabled={$filteredBulk.datasetIndicesResults.length === 0} inactiveClasses='p-4 disabled:text-gray-300'>
        <div slot='title'>
            <span>Gene Exp Across Variables (Bulk)</span>
            <button id="bulk-help">
                <i class='fas fa-circle-question'/>
                <span class="sr-only">Show information</span>
            </button>
        </div>
        <div class="h-[calc(100vh-270px)]">
            <MetadataGraph filteredStore={filteredBulk} heading={$geneInfo?.symbol} allowedPlotTypes={["Violin", "Box"]}/>
        </div>
    </TabItem>
    <TabItem disabled={$filteredVarpart.datasetIndicesResults.length === 0} inactiveClasses='p-4 disabled:text-gray-300'>
        <div slot='title'>
            <span>Drivers of Variation (Bulk)</span>
            <button id="varpart-help">
                <i class='fas fa-circle-question'/>
                <span class="sr-only">Show information</span>
            </button>
        </div>
        <div class="h-[calc(100vh-270px)]">
            <VarpartGraph filteredStore={filteredVarpart} heading={$geneInfo?.symbol}/>
        </div>
    </TabItem>
    <TabItem disabled={$filteredSingleCell.datasetIndicesResults.length === 0} inactiveClasses='p-4 disabled:text-gray-300'>
        <div slot='title'>
            <span>Gene Exp Across Variables (Single Cell)</span>
            <button id="sc-help">
                <i class='fas fa-circle-question'/>
                <span class="sr-only">Show information</span>
            </button>
        </div>

        <div class="h-[calc(100vh-270px)]">
            <MetadataGraph filteredStore={filteredSingleCell} heading={$geneInfo?.symbol} allowedPlotTypes={["Box", "Bar"]} allowSecondMetadataSelect={false}/>
        </div>
    </TabItem>
    <TabItem disabled={$filteredTranscript.datasetIndicesResults.length === 0} inactiveClasses='p-4 disabled:text-gray-300'>
        <div slot='title'>
            <span>Transcript Exp</span>
            <button id="ts-help">
                <i class='fas fa-circle-question'/>
                <span class="sr-only">Show information</span>
            </button>
        </div>
        <div class="h-[calc(100vh-270px)]">
            <TranscriptGraph filteredStore={filteredTranscript} heading={$geneInfo?.symbol}/>
        </div>
    </TabItem>
    <TabItem>
        <div slot='title'>
            <span>Genome Browser</span>
            <button id="gb-help">
                <i class='fas fa-circle-question'/>
                <span class="sr-only">Show information</span>
            </button>
        </div>
        <Genome currentRow={currentRow} filteredStore={filteredStore}/>
    </TabItem>
</Tabs>

<Popover triggeredBy="#exp-help" class="z-[9999] w-[700px] text-sm font-light text-gray-500 bg-white dark:bg-gray-800 dark:border-gray-600 dark:text-gray-400" placement="bottom-start">
    <div class="p-3 space-y-2">
        <h3 class="font-semibold text-gray-900 dark:text-white">Dataset Comparison Details</h3>
        <p>This panel provides information on the overall expression level of the gene in the human brain. Select any two datasets to produce a scatterplot of scaled gene expression values for all genes expressed in both datasets. Each dot represents a gene, with the gene of interest highlighted. For each dataset, gene expression levels are calculated as the mean of log2-transfomed expression values, followed by z-score transformation (subtracting the mean and dividing by the standard deviation).</p>
        <p> For each dataset, z-scores have also been calculated for each region and each developmental period within each dataset. These subsets can be selected using the subset drop down menu. When interpreting these data, note that different datasets include different developmental stages, brain regions, and quantify gene expression by different methods (see Dataset description). </p>
    </div>
</Popover>

<Popover triggeredBy="#bulk-help" class="z-[9999] w-[700px] text-sm font-light text-gray-500 bg-white dark:bg-gray-800 dark:border-gray-600 dark:text-gray-400" placement="bottom-start">
    <div class="p-3 space-y-2">
        <h3 class="font-semibold text-gray-900 dark:text-white">Bulk Cell Details</h3>
        <p>This section allows the detailed exploration of the aggregated brain datasets on BITHub at the gene level from each individual dataset. The expression values (TPM/RPKM) can be plotted against several metadata attributes. By selecting metadata attributes, users have the ability to determine how gene expression of interest varies with any metadata properties such as phenotype (e.g Age, Sex ), sample characteristic or sequencing metrics. Users also have the ability to filter the data based on region by selecting their region of interest from the ‘Select Brain Region’ drop down menu.</p>
        <p>A box plot is generated for categorial metadata and a scatterplot is generated for numerical-based metadata. In the case of numerical variables, a second categorical variable can be selected to color the data points. Users can highlight and select a specific portion of the plot to zoom in, and select or deselect specific metadata annotations by clicking on the legend.</p>
    </div>
</Popover>

<Popover triggeredBy="#varpart-help" class="z-[9999] w-[700px] text-sm font-light text-gray-500 bg-white dark:bg-gray-800 dark:border-gray-600 dark:text-gray-400" placement="bottom-start">
    <div class="p-3 space-y-2">
        <h3 class="font-semibold text-gray-900 dark:text-white">Variance Partition Details</h3>
        <p>View metadata attributes driving variation in a gene of interest across datasets. Drivers of variance were determined using variancePartition (Hoffman,G & Schadt, E).</p>
        <p>The interactive pie charts from each dataset show a fraction of variance explained against the selected metadata. “Unknown” denotes no variancePartition analysis for the given gene in a given dataset due to filtering constraints.</p>
    </div>
</Popover>
  
<Popover triggeredBy="#sc-help" class="z-[9999] w-[700px] text-sm font-light text-gray-500 bg-white dark:bg-gray-800 dark:border-gray-600 dark:text-gray-400" placement="bottom-start">
    <div class="p-3 space-y-2">
        <h3 class="font-semibold text-gray-900 dark:text-white">Single Cell Dataset Details</h3>
        <p>This section allows the detailed exploration of the aggregated single-nucleus datasets on BITHub at the gene from each individual dataset. The CPM expression values can be plotted against several metadata attributes, and users are also able to view cell-type specific expression.</p>
        <p>A box plot is generated for categorial metadata and a scatterplot is generated for numerical-based metadata. In the case of numerical variables, a second categorical variable can be selected to color the data points. Users can highlight and select a specific portion of the plot to zoom in, and select or deselect specific metadata annotations by clicking on the legend.</p>
    </div>
</Popover>

<Popover triggeredBy="#gb-help" class="z-[9999] w-[700px] text-sm font-light text-gray-500 bg-white dark:bg-gray-800 dark:border-gray-600 dark:text-gray-400" placement="bottom-start">
    <div class="p-3 space-y-2">
        <h3 class="font-semibold text-gray-900 dark:text-white">Genone Browser Details</h3>
        <p>Genome Browser track featuring genomic coordinate information from Ensembl, RefSeq and FANTOM5.</p>
    </div>
</Popover>

<Popover triggeredBy="#ts-help" class="z-[9999] w-[700px] text-sm font-light text-gray-500 bg-white dark:bg-gray-800 dark:border-gray-600 dark:text-gray-400" placement="bottom-start">
    <div class="p-3 space-y-2">
        <h3 class="font-semibold text-gray-900 dark:text-white">Transcript Details</h3>
        <p>Heatmap displaying transcript specific expression across different tissues (GTEx) and brain developmental stages (BrainSeq). Values were calculated by averaging expression values per transcript per tissue across all tissues (for GTEx data) or per transcript per age interval (BrainSeq). A z-score normalization has been performed to rank the means. </p>
    </div>
</Popover>