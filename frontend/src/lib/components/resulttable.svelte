<script>
    import Dropdown from './dropdowncheck.svelte';
    import { paginate, LightPaginationNav } from 'svelte-paginate';
    import { gradientCSS, toColorScale, gradientRange } from '../utils/colors'
    import { Button, Tooltip} from 'flowbite-svelte';
    import { createRowWriter } from '../utils/save'
    import { withoutNullsStr } from '../utils/hdf5';

    export let filteredStore;
    export let currentPage;
    export let currentVisible;
    export let currentRow;

    // Custom sorting setup
    let currSort = {list: [], type: 0, id: undefined};
    function toggleSort(e) {
        const newList =  e.target.getAttribute('data-sort-list');
        const newId = e.target.getAttribute('data-sort-id');
        if(newList === null) return;
        if(newId === currSort.id) {
            currSort.type = (currSort.type+1)%3;
        } else {
            currSort.id = newId;
            currSort.list = newList.split(',').map(x => parseInt(x));
            currSort.type = 1;
        }
        currSort = {...currSort}
    }

    function selectRow(e) {
        const row = parseInt(e.target.parentNode.getAttribute('data-row'));
        if(!isNaN(row)) currentRow.set(row);
    }

    // Takes the filteredStore and sorts based on visible selected columns
    let tableData = undefined;
    $: {
        if ( $filteredStore) {
            let sorted = [...$filteredStore.results];
            let columns = $filteredStore.columns;

            // Custom sorting based on either single columns (string comparison) or range of columns (numerical sum)
            if(currSort.id !== undefined && currSort.type) {
                if(currSort.list.length == 1) {
                    const col_i = currSort.list[0];
                    sorted.sort((row_a, row_b) => columns[col_i][row_a] > columns[col_i][row_b] ? -1 : 1);
                } else {
                    const cols = currSort.list.filter(i => $currentVisible.includes($filteredStore.headings[i])).map(i => columns[i]);
                    const avgs = columns[0].map((_, row_i) => cols.map(col => col[row_i]).filter(x => x !== Number.NEGATIVE_INFINITY).reduce((acc, val, i, arr) => (i<arr.length-1) ? acc+val : (acc+val)/arr.length, 0));
                    sorted.sort((row_a, row_b) => avgs[row_b] - avgs[row_a]);
                }
                if(currSort.type == 2) sorted.reverse();
            }

            // We aren't modifying the actual page, just truncating the view
            const page = paginate({items: sorted, pageSize: 50, currentPage: $currentPage > 1 && $currentPage * 50 > sorted.length ? Math.floor(sorted.length/50 + 1) : $currentPage});
            
            tableData = {...$filteredStore, page, sorted, tableSize: sorted.length};
        }
    }

    function downloadTSV(tableData, $filteredStore, currentVisibleIndices) {
        currentVisibleIndices.sort((a, b) => a - b);
        const transformRow = (arr) => arr.map(v => v === -Infinity ? 'NA' : withoutNullsStr(v))
        const tsv = createRowWriter('BITHub.tsv', '\t');
        tsv.write(currentVisibleIndices.map(col_i => $filteredStore.headings[col_i]));
        for(let row_i of tableData.sorted) {
            tsv.write(transformRow(currentVisibleIndices.map(col_i => $filteredStore.columns[col_i][row_i])))
        }
        tsv.close()
    }
</script>

<div class="relative overflow-x-auto">
    {#if tableData }
        {@const currentVisibleIndices = $currentVisible.map(h => tableData.headings.indexOf(h))}
        {@const generalIndicesFiltered = tableData.generalIndices.filter(v => currentVisibleIndices.includes(v))}
        {@const datasetIndicesFiltered = tableData.datasetIndices.filter(v => currentVisibleIndices.includes(v))}
        {@const databaseIndicesFiltered = tableData.databaseIndices.filter(v => currentVisibleIndices.includes(v))}
        <div>
            <span class="absolute m-4 gap-1 flex items-center justify-between items-stretch">
                <Button on:click={() => downloadTSV(tableData, $filteredStore, currentVisibleIndices)} color="light" class="rounded-e-none"><i class="fas fa-download"/></Button>
                <span class="w-64"><Dropdown title="Columns" mainClass="rounded-s-none" groups={tableData.headingGroups} selected={currentVisible} disabled={tableData.headings[0]}/></span>
            </span>
            <table class="table-fixed w-full text-sm text-left rtl:text-right text-gray-500 dark:text-gray-400">
                <thead class="text-xs text-gray-700 uppercase bg-white dark:bg-gray-700 dark:text-gray-400">
                    <tr>
                        <!-- Group headings -->
                        {#each generalIndicesFiltered as i}
                            <!-- N.B Dtype is only used for scaling for relatively small fields so that large ones collapse first-->
                            <th scope="col" class="text-center px-6 py-3 h-24" style={i!=generalIndicesFiltered[0] && (tableData.columnStringSizes[i] ? tableData.columnStringSizes[i] < 20 && `max-width: 300px; width:${tableData.columnStringSizes[i]+8}ch` : 'width:150px')}></th> 
                        {/each}
                        {#if datasetIndicesFiltered.length } 
                            {@const id = 'Datasets'}
                            <th data-sort-id={id} data-sort-list={datasetIndicesFiltered.join(',')} on:click={toggleSort} scope="colgroup" colspan={datasetIndicesFiltered.length} class="cursor-pointer select-none border-b-2 text-center px-6 py-3 whitespace-nowrap overflow-hidden overflow-ellipsis" style="width:{50*datasetIndicesFiltered.length}px">
                                <span class='pointer-events-none'>
                                    <span class="fa-stack fa-1x">
                                        <i class="fa-solid fa-caret-up fa-stack-1x mb-1 {currSort.id === id && currSort.type == 2 ? 'text-gray-800': 'text-gray-300'}"></i>
                                        <i class="fa-solid fa-caret-down fa-stack-1x mt-1 {currSort.id === id && currSort.type == 1 ? 'text-gray-800': 'text-gray-300'}"></i>
                                    </span>
                                    <span class="p-1">{id}</span>
                                </span>
                                <div class='flex flex-col items-center justify-between items-stretch w-[100%] m-auto text-xs normal-case'>
                                    <span class="float-right text-right">{gradientRange[1]} ┐</span>
                                    <div class='bg-red-600 h-[4px] rounded-xl w-full' style="background: linear-gradient(to right, {gradientCSS});"></div>
                                    <span>
                                        <span class='float-left text-left'>└ {gradientRange[0]}</span>
                                        <span class='float-right text-right'>z-scores</span>
                                    </span>
                                </div>
                            </th>
                        {/if}
                        {#if databaseIndicesFiltered.length } 
                            {@const id = 'Databases'}
                            <th data-sort-id={id} data-sort-list={databaseIndicesFiltered.join(',')} on:click={toggleSort} scope="colgroup" colspan={databaseIndicesFiltered.length} class="cursor-pointer select-none border-b-2 text-center px-6 py-3 whitespace-nowrap overflow-hidden overflow-ellipsis" style="width:{50*databaseIndicesFiltered.length}px">
                                <span class='pointer-events-none'>
                                    <span class="fa-stack fa-1x text-gray-300 rotate-180">
                                        <i class="fa-solid fa-caret-up fa-stack-1x mb-1 {currSort.id === id && currSort.type == 2 ? 'text-gray-800': 'text-gray-300'}"></i>
                                        <i class="fa-solid fa-caret-down fa-stack-1x mt-1 {currSort.id === id && currSort.type == 1 ? 'text-gray-800': 'text-gray-300'}"></i>
                                    </span>
                                    <span class="p-1">{id}</span>
                                </span>
                            </th> 
                        {/if}
                    </tr>
                    <tr>
                        <!-- Normal headings -->
                        {#each generalIndicesFiltered as ci}
                            {@const id = tableData.headings[ci]}
                            <th data-sort-id={id} data-sort-list={ci} on:click={toggleSort} scope="col" class="cursor-pointer select-none whitespace-nowrap overflow-hidden overflow-ellipsis">
                                <span class='pointer-events-none'>
                                    <span class="fa-stack fa-1x text-gray-300">
                                        <i class="fa-solid fa-caret-up fa-stack-1x mb-1 {currSort.id === id && currSort.type == 2 ? 'text-gray-800': 'text-gray-300'}"></i>
                                        <i class="fa-solid fa-caret-down fa-stack-1x mt-1 {currSort.id === id && currSort.type == 1 ? 'text-gray-800': 'text-gray-300'}"></i>
                                    </span>
                                    <span class="p-1">{id}</span>
                                </span>
                            </th>
                        {/each}

                        <!-- Rotated headings -->
                        {#each datasetIndicesFiltered.concat(databaseIndicesFiltered) as ci }
                            {@const id = tableData.headings[ci]}
                            <th data-sort-id={id} data-sort-list={ci} on:click={toggleSort} scope="col" class="cursor-pointer select-none align-bottom">
                                <span class='pointer-events-none'>
                                    <span class="p-2 [writing-mode:vertical-lr] scale-[-1] ">{id}</span>
                                    <span class="fa-stack fa-1x text-gray-300">
                                        <i class="fa-solid fa-caret-up fa-stack-1x mb-1 {currSort.id === id && currSort.type == 2 ? 'text-gray-800': 'text-gray-300'}"></i>
                                        <i class="fa-solid fa-caret-down fa-stack-1x mt-1 {currSort.id === id && currSort.type == 1 ? 'text-gray-800': 'text-gray-300'}"></i>
                                    </span>
                                </span>
                            </th>
                        {/each}
                    </tr>
                </thead>
                <tbody>
                    {#each tableData.page as ri}
                        <tr on:click={selectRow} data-row="{ri}" class="cursor-pointer border-t-2 bg-white border-b dark:bg-gray-800 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600">
                            
                            <!-- Normal cells -->
                            {#each generalIndicesFiltered as ci }
                                <td class="px-6 py-4 whitespace-nowrap overflow-hidden overflow-ellipsis">{tableData.columns[ci][ri]}</td>
                            {/each}
                            
                            <!-- Dataset/Database cells -->
                            {#each datasetIndicesFiltered.concat(databaseIndicesFiltered) as ci }
                                {@const zscore = tableData.columns[ci][ri]}
                                {#if zscore !== Number.NEGATIVE_INFINITY }
                                <td class='hover:translate-y-[-3px] group text-center outline outline-1 outline-white rounded-lg shadow-md transition duration-50' style='background-color:{toColorScale(zscore)}'>
                                    <p class="group-hover:opacity-100 opacity-0 z-50 text-black bg-white border rounded-lg text-center transition duration-400 shadow-md cursor-default overflow-hidden" style="text-overflow: ''">{zscore}</p>
                                </td>
                                {:else}
                                    <td class='bg-gray-100/50'>&nbsp</td>
                                {/if}
                            {/each}
                        </tr>
                    {/each}
                </tbody>
            </table>
        </div>
    {:else}
        <!-- Skeleton -->
        <div role="status" class="w-full p-4 space-y-4 border border-gray-200 divide-y divide-gray-200 rounded shadow animate-pulse dark:divide-gray-700 md:p-6 dark:border-gray-700">
            <div class="flex items-center justify-between">
            <div class="w-4/6 h-8 bg-gray-200 rounded-full dark:bg-gray-700"></div>
            <div class="w-1/6 h-12 bg-gray-200 rounded-full dark:bg-gray-700"></div>
            </div>  
            {#each {length: 30} as _}
                <div class="flex items-center justify-between">
                    <div>
                        <div class="h-2.5 bg-gray-300 rounded-full dark:bg-gray-600 w-24 mb-2.5"></div>
                        <div class="w-32 h-2 bg-gray-200 rounded-full dark:bg-gray-700"></div>
                    </div>
                    <div class="h-2.5 bg-gray-300 rounded-full dark:bg-gray-700 w-12"></div>
                </div>
            {/each}
        </div>
    {/if}

    <LightPaginationNav
            totalItems="{tableData?.tableSize}"
            pageSize="{50}"
            currentPage="{$currentPage}"
            limit="{1}"
            showStepOptions="{true}"
            on:setPage={(e) => currentPage.set(e.detail.page)}
        />
</div>