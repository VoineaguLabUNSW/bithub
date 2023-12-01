<script>
    import { getFilteredStoreGroup } from '../stores/results'
    import MetadataGraph from '../components/metadatagraph.svelte';
    import ResultsGraph from '../components/resultgraph.svelte';
    import Genome from '../components/genome.svelte';
    import {Tabs, TabItem } from 'flowbite-svelte';

    export let currentRow;
    export let filteredStore;

    let filteredBulk = getFilteredStoreGroup(filteredStore, 'Gene expression')
    let filteredSingleCell = getFilteredStoreGroup(filteredStore, 'Cell type specific expression')

    let geneName = '';
    $: {
        if($filteredStore && $currentRow !== undefined) {
            geneName = $filteredStore.columns[1][$currentRow];
        }
    }
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
    <TabItem title="Genome Browser">
        <Genome currentRow={currentRow} filteredStore={filteredStore}/>
    </TabItem>
    <TabItem title="Transcript Expression">
        <p class="text-sm text-gray-500 dark:text-gray-400">
            <b>Settings:</b>
            Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
        </p>
    </TabItem>
    <TabItem title="Expression Across Datasets">
        <!-- TODO: hardcoded number of px above to give it defined height and force resizes -->
        <div class="h-[calc(100vh-270px)]">
            <ResultsGraph filteredStore={filteredStore}/>
        </div>
    </TabItem>
    <TabItem open title="Gene Expression">
        <div class="h-[calc(100vh-270px)]">
            <MetadataGraph filteredStore={filteredBulk}/>
        </div>
    </TabItem>
    <TabItem title="Drivers of Variation">
        <p class="text-sm text-gray-500 dark:text-gray-400">
            <b>Settings:</b>
            Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
        </p>
    </TabItem>
    <TabItem title = "Single Cell Datasets ">
        <div class="h-[calc(100vh-270px)]">
            <MetadataGraph filteredStore={filteredSingleCell}/>
        </div>
    </TabItem>
  </Tabs>
