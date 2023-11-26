    
    <script>
    import { page } from '$app/stores';
    import ResultTable from '../../lib/components/resulttable.svelte'
    import ResultGraph from '../../lib/components/resultgraph.svelte'
    import { createParam, createIntParam, createListParam } from '../../lib/stores/param'
    import { getContext } from "svelte";
    import { derived, writable } from 'svelte/store';
    import { Button, Tabs, TabItem, Search, Breadcrumb, BreadcrumbItem  } from 'flowbite-svelte';
    import ProgressHeader from '../../lib/components/progress.svelte'

    
    
    // This component reponds to search parameters, not props
    /*
    let params = {}
    $: {
        const newParams = $page.url.searchParams
        if(newParams !== undefined) {
            const pageInt = parseInt(newParams.get('page'))
            params = {...Object.fromEntries(newParams.entries()), page: pageInt}
        }
        
                    let query = new URLSearchParams($page.url.searchParams.toString());
                    query.set('page', );
                    goto(`?${query.toString()}`);
                }
            }
        
    }*/


    let currentPage = createIntParam('page', 1)
    let currentSearch = createParam('terms', '', v=>v, true)
    let currentVisible = createListParam('visible', ',', true)

    // Fast searches shouldn't polute browser query params/history
    let currentSearchFast = writable([''])
    currentSearch.subscribe(v => currentSearchFast.set(v))

    page.subscribe(p => {
        const newPage = parseInt(p.url.searchParams.get('page'))
        if(!isNaN(newPage) && newPage !== currentPage) currentPage.set(newPage)
    });

    ///derived(page, ($page) => parseInt($page.url.searchParams.get('page')) || 1, 1)
    //const currentSearch = derived(page, ($page) => $page.url.searchParams.get('search') || '', '')

    const {data, getMatrixStore} = getContext('core')

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
        <Search on:blur={(e) => currentSearch.set(e.target.value)} bind:value={$currentSearchFast}/>
        <Button color='light'><i class='fas fa-file-lines'/></Button>
        <Button color='light'><i class='fas fa-plus'/></Button>
    </div>


    <Tabs contentClass='bg-white mt-0 shadow-lg sm:rounded-lg'>
        
        <TabItem open>
            <div slot="title" class="flex items-center gap-2 text-gray-700">
                <i class='fas fa-table-list'></i>
                Results Table
            </div>
            <ResultTable bind:currentPage={currentPage} bind:currentSearch={currentSearchFast} bind:currentVisible={currentVisible}/>
        </TabItem>

        <TabItem>
            <div slot="title" class="flex items-center gap-2 text-gray-700">
                <i class='fas fa-chart-line'></i>
                Results Graph
            </div>
            <ResultGraph bind:currentSearch={currentSearchFast}/>
        </TabItem>
    </Tabs>
</div>
