    
<script>
    import ResultTable from '../../lib/components/resulttable.svelte';
    import ResultGraph from '../../lib/components/resultgraph.svelte';
    import GeneView from '../../lib/components/geneview.svelte';
    import { createParam, createIntParam, createListParam } from '../../lib/stores/param';
    import { createCombinedResultsStore, createFilteredResultsStore, createSelectedResultsStore } from '../../lib/stores/results';
    import { getContext } from "svelte";
    import { derived, writable } from 'svelte/store';
    import { Button, Tabs, TabItem, Search, Breadcrumb, BreadcrumbItem, Modal } from 'flowbite-svelte';
    import ProgressHeader from '../../lib/components/progress.svelte';

    const { row, data } = getContext('core');

    const customDatasets = writable([]);//['Custom dataset 1', 'Custom dataset 2']

    let paramPage = createIntParam('page', 1);
    let paramSearch = createParam('terms', '', v=>v, true);
    let paramVisible = createListParam('visible', ',', true);

    let currentSearch = writable('');
    paramSearch.subscribe(v => currentSearch.set(v));

    let openModal = writable(undefined);
    let currentRow = row;
    currentRow.subscribe(v => v !== undefined && openModal.set(true));
    openModal.subscribe(v => !v && currentRow.set(undefined));

    const combinedStore = createCombinedResultsStore(data, customDatasets);
    const selectedStore = createSelectedResultsStore(combinedStore, row)

    let currentVisibleCombined = ({
        set: paramVisible.set,
        subscribe: derived([paramVisible, combinedStore], ([$v, $c]) => $v?.length ? $v : $c?.headingsDefaultVisible || [], []).subscribe
    })

    const filteredStore = createFilteredResultsStore(combinedStore, currentSearch, currentVisibleCombined);
    
    let sub;
    $: {
        sub = $data?.rowStreams['BrainSeq:RPKM'].current.subscribe(rowData => {
            console.log(rowData)
        })
    }
    
</script>

<ProgressHeader/>
<div class='m-12 mt-4'>
    <div class='pb-4'>
        <Breadcrumb aria-label="Home breadcrumbs">
            <BreadcrumbItem href="/" home>Home</BreadcrumbItem>
            <BreadcrumbItem>Search</BreadcrumbItem>
        </Breadcrumb>
    </div>

    <div class="flex items-center gap-2 items-stretch pb-4">
        <Search on:blur={(e) => paramSearch.set(e.target.value)} bind:value={$currentSearch}/>
        <Button color='light'><i class='fas fa-file-lines'/></Button>
        <Button color='light'><i class='fas fa-plus'/></Button>
    </div>

    <Tabs contentClass='bg-white mt-0 shadow-lg sm:rounded-lg'>
        
        <TabItem open>
            <div slot="title" class="flex items-center gap-2 text-gray-700">
                <i class='fas fa-table-list'></i>
                Results Table
            </div>
            <ResultTable filteredStore={filteredStore} bind:currentPage={paramPage} bind:currentVisible={currentVisibleCombined} bind:currentRow={currentRow}/>
        </TabItem>

        <TabItem>
            <div slot="title" class="flex items-center gap-2 text-gray-700">
                <i class='fas fa-chart-line'></i>
                Results Graph
            </div>
            <!-- TODO: hardcoded number of px above to give it defined height and force resizes -->
            <div class="h-[calc(100vh-214px)]">
                <ResultGraph filteredStore={filteredStore}/>
            </div>
        </TabItem>
    </Tabs>
</div>

<Modal bind:open={$openModal} size='xl' outsideclose={true}>
    <GeneView filteredStore={selectedStore} currentRow={currentRow}></GeneView>
</Modal>
