    
    <script>
    import { page } from '$app/stores';
    import ResultTable from '../../lib/components/resulttable.svelte'
    import ResultGraph from '../../lib/components/resultgraph.svelte'
    import { createParam, createIntParam, createListParam } from '../../lib/stores/param'
    import { createCombinedStore, createFilteredStore } from '../../lib/stores/results'
    import { getContext } from "svelte";
    import { derived, writable } from 'svelte/store';
    import { Button, Tabs, TabItem, Search, Breadcrumb, BreadcrumbItem  } from 'flowbite-svelte';
    import ProgressHeader from '../../lib/components/progress.svelte'

    const customDatasets = writable(['Custom dataset 1', 'Custom dataset 2']);

    let paramPage = createIntParam('page', 1)
    let paramSearch = createParam('terms', '', v=>v, true)
    let paramVisible = createListParam('visible', ',', true)

    let currentSearch = writable('')
    paramSearch.subscribe(v => currentSearch.set(v))

    const {data, getMatrixStore} = getContext('core')
    const combinedStore = createCombinedStore(data, customDatasets)

    let currentVisibleCombined = ({
        set: paramVisible.set,
        subscribe: derived([paramVisible, combinedStore], ([$v, $c]) => $v?.length ? $v : $c?.headingsDefaultVisible || [], []).subscribe
    })

    const filteredStore = createFilteredStore(combinedStore, currentSearch, currentVisibleCombined)

    let dataset = 'BrainSeq'
    let matrix = 'RPKM'
    let unsub = undefined;
    let expression = undefined;
    $: {
        if($data?.value) {
            unsub = getMatrixStore(dataset, matrix).subscribe((data) => {
                if(unsub) unsub()
                expression = data
            })
        }
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
            <ResultTable filteredStore={filteredStore} bind:currentPage={paramPage} bind:currentVisible={currentVisibleCombined}/>
        </TabItem>

        <TabItem>
            <div slot="title" class="flex items-center gap-2 text-gray-700">
                <i class='fas fa-chart-line'></i>
                Results Graph
            </div>
            <ResultGraph filteredStore={filteredStore}/>
        </TabItem>
    </Tabs>
</div>