<script>
    import Dropdown from '../components/dropdown.svelte';
    import Plot from '../components/plot.svelte';
    import { writable } from "@square/svelte-store";
    import { getContext } from "svelte";
    import { derived } from 'svelte/store';
    import { getPlotEmpty } from '../utils/plot';

    export let filteredStore;
    export let heading;

    const { data } = getContext('core');

    let datasetsSelect = writable();

    const datasetOptsObj = derived([data, filteredStore], ([$data, $filteredStore], set) => {
        if(!$data || !$filteredStore) return;
        const datasetOptVals = $filteredStore.datasetIndicesResults.map(col_i => $filteredStore.headings[col_i]).map(h => ({id: h, name: h}));
        const datasetsOpts = new Map([['', datasetOptVals]]);
        datasetsSelect.set(datasetOptVals[0]);
        set({$data, datasetsOpts});
    });

    const varianceDataObj = derived([datasetOptsObj, datasetsSelect], ([$datasetOptsObj, $datasetsSelect], set) => {
        if(!$datasetOptsObj || !$datasetsSelect?.id) return;
        const rowStream = $datasetOptsObj.$data.rowStreams['/metadata/' +  $datasetsSelect.id + '/variance_partition']
        const headings = rowStream.attrs.heading;
        const expressionSub = rowStream.current.subscribe(varpart => {
            if(varpart) set({$datasetOptsObj, varpart, headings})
        })
        return () => expressionSub()
    })

    const plotlyArgs = derived(varianceDataObj, ($varianceDataObj, set) => {
        if(!$varianceDataObj) set(getPlotEmpty('No data'));
        else if($varianceDataObj.varpart.loading) set(getPlotEmpty('Loading'));
        else {
            set({
                plotData: [{
                    type: 'bar',
                    x: $varianceDataObj.headings,
                    y: $varianceDataObj.varpart.data.values,
                    orientation: 'v',
                    marker: {
                        color: self.variancePartitionColor
                    }
                }],
                layout: { 
                    showlegend: false,
                    title: {
                        text: heading + ` - ${$datasetsSelect?.id}`,
                        font: { family: "Times New Roman", size: 20 },
                    },
                    xaxis: {
                        title: {
                            text: 'Metadata Variable',
                            font: { family: 'Times New Roman', size: 18, color: '#7f7f7f' }
                        },
                    },
                    yaxis: {
                        title: {
                            text: 'Fraction Variance Explained',
                            font: { family: 'Times New Roman', size: 18, color: '#7f7f7f' }
                        }
                    },
                }
            
            })
        }
    
    })
</script>

<Plot plotlyArgs={plotlyArgs}>
    <span slot="controls">
        <div class="flex justify-between">
            <h5 id="drawer-label" class="inline-flex items-center mb-4 text-base font-semibold text-gray-500 dark:text-gray-400">
                <i class='fas fa-gears m-2'/>Dataset
            </h5>
        </div>
        <div class='w-48 flex flex-col items-stretch gap-3'>
            <Dropdown title='Dataset' selected={datasetsSelect} groups={$datasetOptsObj.datasetsOpts}/>
        </div>
    </span>
</Plot>