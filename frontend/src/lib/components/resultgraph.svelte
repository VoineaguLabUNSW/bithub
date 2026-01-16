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
        const datasetAvail = $filteredStore.datasetIndicesResults.map(col_i => $filteredStore.headings[col_i]);
        const datasetOptVals = datasetAvail.map(h => ({id: h, name: h}));
        const datasetOpts = new Map([['', datasetOptVals]]);

        set({datasetOpts, $filteredStore})

        if(!datasetAvail.includes(get(datasetSelect1)?.id)) datasetSelect1.set(datasetOptVals[0]);
        if(!datasetAvail.includes(get(datasetSelect2)?.id)) datasetSelect2.set(datasetOptVals[1]);
        
    });

    function createFilterObj(datasetSelect, filterSelect) {
        return derived([datasetSelect, data], ([datasetSelect, data], set) => {
            if(!datasetSelect || !data) return;
            if(!data.value.get('metadata').keys.includes(datasetSelect.id)) {
                filterSelect.set(undefined)
                set({ filterOpts: new Map([['', []]])})
            } else {
                const {customFilterCategory, customFilterName} = data.value.get('metadata/' + datasetSelect.id + '/zscores').attrs;
                const filterOptVals = customFilterCategory.map(h => ({id: datasetSelect.id + '|' + h, name: h}));
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
        let [ds1, fl1] = [$datasetSelect1.id, 'All']
        if($filterSelect1) [ds1, fl1] = $filterSelect1.id.split('|', 2);
        let [ds2, fl2] = [$datasetSelect2.id, 'All']
        if($filterSelect2) [ds2, fl2] = $filterSelect2.id.split('|', 2);

        if(ds1 !== $datasetSelect1.id || ds2 !== $datasetSelect2.id) return;

        const xAll = fl1 !== 'All' ? $data.value.get('metadata/' + ds1 + '/zscores/' + fl1).value : $filteredStore.columns[$filteredStore.headings.indexOf(ds1)];
        const yAll = fl2 !== 'All' ? $data.value.get('metadata/' + ds2 + '/zscores/' + fl2).value : $filteredStore.columns[$filteredStore.headings.indexOf(ds2)];
        
        const x = $filteredStore.results.map(row_i => xAll[row_i]);
        const y = $filteredStore.results.map(row_i => yAll[row_i]);
        
        const names = $filteredStore.results.map(row_i => withoutNullsStr($filteredStore.columns[1][row_i]));
        let xName = ds1 + (fl1 == 'All' ? '' : ` (${fl1})`);
        let yName = ds2 + (fl2 == 'All' ? '' : ` (${fl2})`);

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
            <Dropdown title='Dataset 1' placeholder='No Datasets' selected={datasetSelect1} groups={$datasetsObj.datasetOpts}/>
            <Dropdown title='Dataset 2' placeholder='No Datasets' selected={datasetSelect2} groups={$datasetsObj.datasetOpts}/>
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
