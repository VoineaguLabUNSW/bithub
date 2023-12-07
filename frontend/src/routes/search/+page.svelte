    
<script>
    import ResultTable from '../../lib/components/resulttable.svelte';
    import ResultGraph from '../../lib/components/resultgraph.svelte';
    import GeneView from '../../lib/components/geneview.svelte';
    import CustomView from '../../lib/components/customview.svelte';
    import DropdownFile from '../../lib/components/dropdownfile.svelte'
    import { base } from '$app/paths';
    import { findMatchesSorted } from "../../lib/utils/hdf5";
    import { asCSV } from '../../lib/stores/custom'
    import { createParam, createIntParam, createListParam } from '../../lib/stores/param';
    import { createCombinedResultsStore, createFilteredResultsStore, createSelectedResultsStore, getFilteredStoreAll } from '../../lib/stores/results';
    import { getContext, onDestroy } from "svelte";
    import { derived, writable } from 'svelte/store';
    import { Button, Tabs, TabItem, Search, Breadcrumb, BreadcrumbItem, Modal } from 'flowbite-svelte';
    import { disableBodyScroll, enableBodyScroll, clearAllBodyScrollLocks } from 'body-scroll-lock';
    import ProgressHeader from '../../lib/components/progress.svelte';

    const { row, data, customs } = getContext('core');

    const userFilterFiles = writable(undefined);
    const userFilterFileActive = writable(true);
    const userFilterContent = asCSV(userFilterFiles, false, 1, 1)
    const userFilterColumn = derived([data, userFilterContent], ([$data, $userFilterContent], set) => {
        if(!$userFilterContent?.result || !$data?.value) return;
        const headings = $data.value.get('data').attrs.order;
        const ensemblIds = $data.value.get('data/' + headings[0]).value;
        const userEnsemblIds = $userFilterContent.result.map(row => row[0]);
        const ensemblMatches = findMatchesSorted([ensemblIds], userEnsemblIds);
        if(ensemblMatches.length == 0) {
            set({error: 'No strings in the first column matched to Ensembl IDs'});
        } else {
            set({result: ensemblMatches.map(m => m.rowIndex)})
        }
    })
    const userFilterIndices = derived([userFilterColumn, userFilterFileActive], ([$userFilterColumn, $userFilterFileActive]) => {
        return $userFilterFileActive ? $userFilterColumn?.result : undefined;
    });

    let paramPage = createIntParam('page', 1);
    let paramSearch = createParam('terms', '', v=>v, true);
    let paramVisible = createListParam('visible', ',', true);
    let paramModal = createParam('open', '', v=>v, true);

    let currentSearch = writable('');
    paramSearch.subscribe(v => currentSearch.set(v));

    let customModalElement;

    let openGeneView = writable(undefined);
    let currentRow = row;
    currentRow.subscribe(v => v !== undefined && openGeneView.set(true));
    openGeneView.subscribe(v => !v && currentRow.set(undefined));
    
    const combinedStore = createCombinedResultsStore(data, customs);
    const selectedStore = createSelectedResultsStore(combinedStore, row)

    let currentVisibleCombined = ({
        set: paramVisible.set,
        subscribe: derived([paramVisible, combinedStore], ([$v, $c]) => $v?.length ? $v : $c?.headingsDefaultVisible || [], []).subscribe
    })

    const filteredStore = createFilteredResultsStore(combinedStore, currentSearch, currentVisibleCombined, userFilterIndices);
    const filteredStoreAll = getFilteredStoreAll(filteredStore);

    let geneModalElement;

    openGeneView.subscribe(v => geneModalElement && (v ? disableBodyScroll(geneModalElement) : enableBodyScroll(geneModalElement)))
    paramModal.subscribe(v => customModalElement && (v ? disableBodyScroll(customModalElement) : enableBodyScroll(customModalElement)))
    onDestroy(clearAllBodyScrollLocks);
    
</script>

<ProgressHeader/>
<div class='m-12 mt-4'>
    <div class='pb-4'>
        <Breadcrumb aria-label="Home breadcrumbs">
            <BreadcrumbItem href="{base}" home>Home</BreadcrumbItem>
            <BreadcrumbItem>Search</BreadcrumbItem>
        </Breadcrumb>
    </div>

    <div class="flex items-center gap-1 items-stretch pb-4">
        <DropdownFile files={userFilterFiles} active={userFilterFileActive} mainClass='rounded-e-none max-w-[150px] min-w-[150px]' color='dark' title='Filter...' error={$userFilterColumn?.error || $userFilterContent?.error} help='First column should be Ensembl IDs or gene symbols.'></DropdownFile>
        <Search class='rounded-none' on:blur={(e) => paramSearch.set(e.target.value)} bind:value={$currentSearch}/>
        <Button class='rounded-s-none' on:click={() => paramModal.set('custom')} color='dark'><i class='fas fa-plus'/></Button>
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
                <ResultGraph filteredStore={filteredStoreAll} heading={'Z-Score Transformed Mean Log2 (Expression)'}/>
            </div>
        </TabItem>
    </Tabs>
</div>

<Modal bind:this={geneModalElement} bind:open={$openGeneView} size='xl' outsideclose={true} class='overscroll-contain'>
    <GeneView filteredStore={selectedStore} currentRow={currentRow}></GeneView>
</Modal>

<Modal bind:this={customModalElement} title="Add Custom Dataset" open={$paramModal == 'custom'} outsideclose={true} on:close={() => paramModal.set('')}>
    <CustomView customModal={paramModal}/>
</Modal>