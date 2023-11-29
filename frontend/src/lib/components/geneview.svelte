<script>
    import ResultGraph from '../components/resultgraph.svelte'
    import Genome from '../components/genome.svelte'
    import { Button, Tabs, TabItem, Search, Breadcrumb, BreadcrumbItem, Modal } from 'flowbite-svelte';

    export let currentRow;
    export let filteredStore;

    let geneName = ''
    $: {
        if($filteredStore && $currentRow !== undefined) {
            geneName = $filteredStore.columns[1][$currentRow]
        }
    }
    
</script>


<style>
    :global(.igv-chromosome-select-widget-container > select) {
        padding-top: 0px;
    }
</style>

<div class='flex gap-2 items-center'>
    <div class='text-3xl'>{$filteredStore.columns[1][$currentRow]}</div><div>{'(' + $filteredStore.columns[0][$currentRow] + ')'}</div>
</div>
<div class='text-lg'>{$filteredStore.columns[2][$currentRow]}</div>
<hr>

<!-- TODO: hardcoded number of px above to give it defined height and force resizes -->
<div class="h-[calc(100vh-218px)]">
  <ResultGraph filteredStore={filteredStore}/>
</div>

<!--
<Tabs contentClass='bg-white mt-0 shadow-lg sm:rounded-lg h-[calc(90vh-200px)]'>
    <TabItem open title="Genome Browser">
        <Genome currentRow={currentRow} filteredStore={filteredStore}/>
    </TabItem>
    <TabItem title="Transcripts">
      <p class="text-sm text-gray-500 dark:text-gray-400">
        <b>Settings:</b>
        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
      </p>
    </TabItem>
    <TabItem title="Expression Across Datasets">
        <ResultGraph filteredStore={filteredStore}/>
    </TabItem>
    <TabItem title="Bulk Datasets">
      <p class="text-sm text-gray-500 dark:text-gray-400">
        <b>Dashboard:</b>
        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
      </p>
    </TabItem>
    <TabItem title = "Single Cell Datasets ">
      <p class="text-sm text-gray-500 dark:text-gray-400">
        <b>Disabled:</b>
        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
      </p>
    </TabItem>
  </Tabs>
-->