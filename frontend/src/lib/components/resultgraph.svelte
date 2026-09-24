<script>
    import { getPlotEmpty, getColumnDownloader, getZipped, getWithNA } from '../utils/plot';
    import Dropdown from '../components/dropdown.svelte';
    import Plot from '../components/plot.svelte';
    import { writable, get, derived } from "svelte/store";
    import { getContext } from 'svelte';
    import { withoutNullsStr } from '$lib/utils/hdf5';
   
    export let filteredStore;
    export let heading;

    const { data } = getContext('core');
    const { colorPrimary } = getContext('displaySettings');

    let datasetSelect1 = writable();
    let datasetSelect2 = writable();

    let filterSelect1 = writable();
    let filterSelect2 = writable();

    // Initial data parse
    const datasetsObj = derived(filteredStore, ($filteredStore, set) => {
        if(!$filteredStore) return;
        const datasetOptVals = $filteredStore.datasetIndicesResults.map(col_i => $filteredStore.headings[col_i]);
        const datasetOpts = new Map([['', datasetOptVals]]);

        set(datasetOpts);
        datasetSelect1.update(current => datasetOptVals.includes(current) ? current : datasetOptVals[0]);
        datasetSelect2.update(current => datasetOptVals.includes(current) ? current : datasetOptVals[1]);
    });

    function createFilterObj(datasetSelect, filterSelect) {
        return derived([datasetSelect, data], ([datasetSelect, data], set) => {
            if(!datasetSelect || !data) return;
            if(!data.value.get('metadata').keys.includes(datasetSelect)) {
                // N.B. Custom datasets have no filter options
                filterSelect.set('All')
                set({ filterOpts: new Map([['', []]])})
            } else {
                const {customFilterCategory, customFilterName} = data.value.get('metadata/' + datasetSelect + '/zscores').attrs;
                const filterOptVals = customFilterCategory;
                filterSelect.set(filterOptVals[0]);
                set({title: customFilterName, filterOpts: new Map([['', filterOptVals]])})
            }
        });
    }

    const filterObj1 = createFilterObj(datasetSelect1, filterSelect1);
    const filterObj2 = createFilterObj(datasetSelect2, filterSelect2);

    const plotlyArgs = derived([datasetSelect1, datasetSelect2, filterSelect1, filterSelect2, data, filteredStore, colorPrimary], ([$datasetSelect1, $datasetSelect2, $filterSelect1, $filterSelect2, $data, $filteredStore, $colorPrimary], set) => {
        if(!$datasetSelect1 || !$datasetSelect2 || !$data) {
            set(getPlotEmpty('No data'));
            return
        }
        
        const xAll = $filterSelect1 !== 'All' ? $data.value.get('metadata/' + $datasetSelect1 + '/zscores/' + $filterSelect1).value : $filteredStore.columns[$filteredStore.headings.indexOf($datasetSelect1)];
        const yAll = $filterSelect2 !== 'All' ? $data.value.get('metadata/' + $datasetSelect2 + '/zscores/' + $filterSelect2).value : $filteredStore.columns[$filteredStore.headings.indexOf($datasetSelect2)];

        const x = $filteredStore.results.map(row_i => xAll[row_i]);
        const y = $filteredStore.results.map(row_i => yAll[row_i]);
        
        const names = $filteredStore.results.map(row_i => withoutNullsStr($filteredStore.columns[1][row_i]));
        let xName = $datasetSelect1 + ($filterSelect1 == 'All' ? '' : ` (${$filterSelect1})`);
        let yName = $datasetSelect2 + ($filterSelect2 == 'All' ? '' : ` (${$filterSelect2})`);

        let extraMarkerArgs = {}
        if(names.length == 1) {
            extraMarkerArgs = {
                line: { color: 'white', width: 1 },
                size: 15
            }
        }

        set({
                plotData: [{
                        mode: 'markers',
                        type: 'scattergl',
                        x: xAll,
                        y: yAll,
                        hoverinfo: 'skip',
                        marker : {color: 'lightgray'}
                    },{
                        mode: 'markers',
                        type: 'scattergl',
                        name: '',
                        x: x,
                        y: y,
                        marker : {color: $colorPrimary[0], ...extraMarkerArgs},
                        text: names,
                        hoverlabel: { bgcolor: "white" },
                    }
                ],
                layout: { 
                    showlegend: false,
                    title: {
                        text: heading,
                        font: { family: "Times New Roman", size: 20 },
                    },
                    xaxis: {
                        title: {
                            text: xName,
                            font: { family: 'Times New Roman', size: 18, color: '#7f7f7f' }
                        },
                    },
                    yaxis: {
                        title: {
                            text: yName,
                            font: { family: 'Times New Roman', size: 18, color: '#7f7f7f' }
                        }
                    },
                },
                downloadCSV: getColumnDownloader(heading, getZipped({x: getWithNA(x), y: getWithNA(y), name: names}), xName, yName)
            }
        )
        
    });
</script>

<Plot plotlyArgs={plotlyArgs}>
    <svelte:fragment slot="title">
        <i class='fas fa-gears'/> Datasets
    </svelte:fragment>
    <svelte:fragment slot="controls">
        <p class="mb-6 text-sm text-gray-500 dark:text-gray-400">
            Select from different datasets to compare z-scores for any number of search results.
        </p>
        <div class='w-48 flex flex-col items-stretch gap-3'>
            <Dropdown title='Dataset 1' placeholder='No Datasets' selected={datasetSelect1} groups={$datasetsObj}/>
            <Dropdown title='Dataset 2' placeholder='No Datasets' selected={datasetSelect2} groups={$datasetsObj}/>
            <hr>
            {#if $filterObj1?.title }
                <Dropdown title={'Dataset 1 Subset (' + $filterObj1.title + ')'} selected={filterSelect1} groups={$filterObj1.filterOpts}/>
            {/if}
            {#if $filterObj2?.title }
                <Dropdown title={'Dataset 2 Subset (' + $filterObj2.title + ')'} selected={filterSelect2} groups={$filterObj2.filterOpts}/>
            {/if}
        </div>
    </svelte:fragment>
</Plot>
