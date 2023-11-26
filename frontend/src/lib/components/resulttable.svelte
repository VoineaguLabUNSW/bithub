<script>
    import { getContext } from "svelte";
    import Dropdown from './dropdown.svelte'
    import { paginate, LightPaginationNav } from 'svelte-paginate'
    import chroma from "chroma-js";
    import { Button } from 'flowbite-svelte';
    import { writable, derived } from 'svelte/store';

    export let customDatasets = writable(['Custom dataset 1', 'Custom dataset 2']);
    export let currentPage;
    export let currentSearch;
    export let currentVisible;

    // Prevent loaded default from triggering currentVisible.set (query parameters should only be from user action)
    const currentVisibleDefault = writable([]);
    const currentVisibleCombined = ({
        set: currentVisible.set,
        subscribe: derived([currentVisible, currentVisibleDefault], ([$v, $d]) => $v?.length ? $v : $d, []).subscribe
    })

    const { data } = getContext('core')

    // Heatmap setup
    const scale = chroma.scale(['purple', 'orange']);
    function toColorScale(v, min, max) {
        v = Math.max(Math.min(v, max), min)
        return scale((v-min)/max).hex()
    }

    // Custom sorting setup
    let currSort = {list: [], type: 0, id: undefined}
    function toggleSort(e) {
        const newList =  e.target.getAttribute('data-sort-list');
        const newId = e.target.getAttribute('data-sort-id')
        if(newList === null) return
        if(newId === currSort.id) {
            currSort.type = (currSort.type+1)%3
        } else {
            currSort.id = newId
            currSort.list = newList.split(',').map(x => parseInt(x))
            currSort.type = 1;
        }
        currSort = {...currSort}
    }

    // Main table loading
    let tableSource = undefined
    $: {
        if($data?.value) {
            const headings = $data.value.get('data').attrs.order;
            const original = headings.map(k => $data.value.get('data/' + k).value);
            const [isDs, isDb] = [$data.value.get('data').attrs.isDataset, $data.value.get('data').attrs.isDatabase]
            const indices = headings.map((h, i) => (isDs[i] || isDb[i]) ? $data.value.get('metadata/' + h + '/scaled').value : undefined)
            const columnStringSizes = headings.map(k => $data.value.get('data/' + k).dtype).map(dt => dt.startsWith('S') ? parseInt(dt.slice(1)) : undefined);
            currentVisibleDefault.set($data.value.get('data').attrs.defaultVisible.map(i => headings[i]))

            for(let h of $customDatasets) {
                const insertPoint = isDs.indexOf(1)
                headings.splice(insertPoint, 0, h)
                original.splice(insertPoint, 0, new Array(original[0].length).fill(0))
                isDs.splice(insertPoint, 0, 1)
                indices.splice(insertPoint, 0, [3.8])
                columnStringSizes.splice(insertPoint, 0, undefined)
            }

            const boolToIndices = (array) => array.map((v, i) => v ? i : undefined).filter(x => x !== undefined);
            const datasetIndices = boolToIndices(isDs)
            const databaseIndices = boolToIndices(isDb)
            const generalIndices = boolToIndices(headings.map((_, i) => !isDs[i] && !isDb[i]))
            
            const columns = [...generalIndices.map(i => original[i]), ...datasetIndices.concat(databaseIndices).map(col_i => original[col_i].map(v => v === -1 ? Number.NEGATIVE_INFINITY : indices[col_i][v]))]
            const headingGroups = new Map([['', generalIndices.map(i => headings[i])], ['Datasets', datasetIndices.map(i => headings[i])], ['Databases', databaseIndices.map(i => headings[i])]])
            tableSource = {headings, columns, generalIndices, datasetIndices, databaseIndices, columnStringSizes, headingGroups}
        }
    }

    // Main table filtering and sorting
    let tableData = undefined;
    $: {
        if ( tableSource) {
            const columns = tableSource.columns;
            let sorted = Array.from(Array(columns[0].length).keys());

            // Filter before sorting
            const newSearch = $currentSearch
            if(newSearch) {
                const searchTerms = newSearch.split(',').map(st => st.trim().toLowerCase())
                searchTerms.sort()

                if(searchTerms.length == 1) {
                    const searchable = tableSource.columns.map((_, col_i) => col_i).filter(col_i => tableSource.columnStringSizes[col_i]).filter(col_i => $currentVisibleCombined.includes(tableSource.headings[col_i]))
                    sorted = sorted.filter(row_i => searchable.some(col_i => tableSource.columns[col_i][row_i].toLowerCase().includes(searchTerms[0])))
                } else {
                    function findMatchesSorted(arrays, searches) {
                        searches.sort();
                        arrays.forEach(a => a.sort());
                        let indices = new Array(arrays.length).fill(0)
                        let ret = []
                        for(const term of searches) {
                            for(const [i, arr] of arrays.entries()) {
                                let cmp = -1;
                                while(indices[i]<arr.length && cmp < 0) {
                                    cmp = arr[indices[i]].localeCompare(term, undefined, { sensitivity: 'accent' })
                                    if(cmp < 0) indices[i]++;
                                }
                                if (cmp === 0) {
                                    ret.push(indices[i]);
                                    break;
                                }
                            }
                        }
                        return ret;
                    }
                    const exactSearchable = [0, 1].filter(col_i => $currentVisibleCombined.includes(tableSource.headings[col_i])).map(col_i => columns[col_i])
                    sorted = findMatchesSorted(exactSearchable, searchTerms);
                }
            }

            // ----- From here on should be inside table component

            // Custom sorting based on either single columns (string comparison) or range of columns (numerical sum)
            if(currSort.id !== undefined && currSort.type) {
                if(currSort.list.length == 1) {
                    const col_i = currSort.list[0];
                    sorted.sort((row_a, row_b) => columns[col_i][row_a] > columns[col_i][row_b] ? -1 : 1)
                } else {
                    const cols = currSort.list.filter(i => $currentVisibleCombined.includes(tableSource.headings[i])).map(i => columns[i])
                    const avgs = columns[0].map((_, row_i) => cols.map(col => col[row_i]).filter(x => x !== Number.NEGATIVE_INFINITY).reduce((acc, val, i, arr) => (i<arr.length-1) ? acc+val : (acc+val)/arr.length, 0))
                    sorted.sort((row_a, row_b) => avgs[row_b] - avgs[row_a])
                }
                if(currSort.type == 2) sorted.reverse();
            }

            // We aren't modifying the actual page, just truncating the view
            const page = paginate({items: sorted, pageSize: 50, currentPage: $currentPage > 1 && $currentPage * 50 > sorted.length ? Math.floor(sorted.length/50 + 1) : $currentPage})
            tableData = {...tableSource, page, tableSize: sorted.length}
        }
    }
</script>

<div class="relative overflow-x-auto">
    {#if tableData }
        {@const currentVisibleIndices = $currentVisibleCombined.map(h => tableData.headings.indexOf(h))}
        {@const generalIndicesFiltered = tableData.generalIndices.filter(v => currentVisibleIndices.includes(v))}
        {@const datasetIndicesFiltered = tableData.datasetIndices.filter(v => currentVisibleIndices.includes(v))}
        {@const databaseIndicesFiltered = tableData.databaseIndices.filter(v => currentVisibleIndices.includes(v))}
        <div>
            <span class="absolute m-4 gap-4 flex items-center justify-between items-stretch">
                <Button color="light"><i class="fas fa-upload"/></Button>
                <Button color="light"><i class="fas fa-download"/></Button>
                <span class="w-64"><Dropdown title="Columns" groups={tableData.headingGroups} selected={currentVisibleCombined} disabled={tableData.headings[0]}/></span>
            </span>
            <table class="table-fixed w-full text-sm text-left rtl:text-right text-gray-500 dark:text-gray-400">
                <thead class="text-xs text-gray-700 uppercase bg-white dark:bg-gray-700 dark:text-gray-400">
                    <tr>
                        <!-- Group headings -->
                        {#each generalIndicesFiltered as i}
                            <!-- N.B Dtype is only used for scaling for relatively small fields so that large ones collapse first-->
                            <th scope="col" class="text-center px-6 py-3 h-24"  style={i!=generalIndicesFiltered[0] && (tableData.columnStringSizes[i] ? tableData.columnStringSizes[i] < 20 && `max-width: 300px; width:${tableData.columnStringSizes[i]+8}ch` : 'width:150px')}></th> 
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
                        {#each generalIndicesFiltered as i}
                            {@const id = tableData.headings[i]}
                            <th data-sort-id={id} data-sort-list={i} on:click={toggleSort} scope="col" class="cursor-pointer select-none whitespace-nowrap overflow-hidden overflow-ellipsis">
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
                        {#each datasetIndicesFiltered.concat(databaseIndicesFiltered) as i }
                            {@const id = tableData.headings[i]}
                            <th data-sort-id={id} data-sort-list={i} on:click={toggleSort} scope="col" class="cursor-pointer select-none align-bottom">
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
                        <tr class="border-t-2 bg-white border-b dark:bg-gray-800 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600">
                            
                            <!-- Normal cells -->
                            {#each generalIndicesFiltered as ci }
                                <td class="px-6 py-4 whitespace-nowrap overflow-hidden overflow-ellipsis">{tableData.columns[ci][ri]}</td>
                            {/each}
                            
                            <!-- Dataset/Database cells -->
                            {#each datasetIndicesFiltered.concat(databaseIndicesFiltered) as ci }
                                {@const zscore = tableData.columns[ci][ri]}
                                {#if zscore !== Number.NEGATIVE_INFINITY }
                                <td class='hover:translate-y-[-3px] group text-center outline outline-1 outline-white rounded-lg shadow-md transition duration-50' style='background-color:{toColorScale(zscore, -2, 7)}'>
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