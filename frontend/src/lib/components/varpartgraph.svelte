<script>
    import Dropdown from '../components/dropdown.svelte';
    import Plot from '../components/plot.svelte';
    import { writable } from "@square/svelte-store";
    import { getContext } from "svelte";
    import { derived } from 'svelte/store';
    import { getPlotEmpty, getPlotBar } from '../utils/plot';

    export let filteredStore;
    export let heading;

    const { data } = getContext('core');
    const { colorPrimary } = getContext('displaySettings')

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

    const plotlyArgs = derived([varianceDataObj, colorPrimary], ([$varianceDataObj, $colorPrimary], set) => {
        if(!$varianceDataObj) set(getPlotEmpty('No data'));
        else if($varianceDataObj.varpart.loading) set(getPlotEmpty('Loading'));
        else if($varianceDataObj.varpart.error) set(getPlotEmpty($varianceDataObj.varpart.error));
        else set(getPlotBar(heading + ` - ${$datasetsSelect?.id}`, $varianceDataObj.headings, $varianceDataObj.varpart.data.values, 'Metadata Variable', 'Fraction Variance Explained', $colorPrimary[0]));
    })
</script>

<Plot plotlyArgs={plotlyArgs}>
    <svelte:fragment slot="title">
        <i class='fas fa-gears'/> Dataset
    </svelte:fragment>
    <span slot="controls">
        <div class='w-48 flex flex-col items-stretch gap-3'>
            <Dropdown title='Dataset' selected={datasetsSelect} groups={$datasetOptsObj.datasetsOpts}/>
        </div>
    </span>
</Plot>