<script>
    import Dropdown from '../components/dropdown.svelte';
    import Plot from '../components/plot.svelte';
    import { writable } from "@square/svelte-store";
    import { getContext } from "svelte";
    import { derived } from 'svelte/store';
    import { getPlotEmpty, getTablDownloader } from '../utils/plot';
    import { withoutNullsStr } from '$lib/utils/hdf5';

    export let filteredStore;
    export let heading;

    const { data } = getContext('core');

    let datasetsSelect = writable();
    let transcriptSelect = writable();
    
    let scaleSelect = writable({id: 'Linear', name: 'Linear'});
    const scaleOpts = new Map([['', ['Linear', 'Log e', 'Log 10'].map(l => ({id: l, name: l}))]])


    const datasetOptsObj = derived([data, filteredStore], ([$data, $filteredStore], set) => {
        if(!$data || !$filteredStore) return;
        const datasetOptVals = $filteredStore.datasetIndicesResults.map(col_i => $filteredStore.headings[col_i]).map(h => ({id: h, name: h}));
        const datasetsOpts = new Map([['', datasetOptVals]]);
        datasetsSelect.set(datasetOptVals[0]);
        set({$data, datasetsOpts});
    });

    const transcriptOptsObj = derived([datasetOptsObj, datasetsSelect], ([$datasetOptsObj, $datasetsSelect], set) => {
        if(!$datasetOptsObj || !$datasetsSelect) return;

        const transcriptOptVals = $datasetOptsObj.$data.value.get('metadata/' + $datasetsSelect.name + '/transcripts').attrs.order.map(v => ({id: $datasetsSelect.id + '|' + v, name: v}))
        const transcriptOpts = new Map([['', transcriptOptVals]]);
        transcriptSelect.set(transcriptOptVals[0]);
        set({...$datasetOptsObj, $datasetsSelect, transcriptOpts})
    })

    const expressionDataObj = derived([transcriptOptsObj, transcriptSelect], ([$transcriptOptsObj, $transcriptSelect], set) => {
        if(!$transcriptOptsObj || !$transcriptSelect?.id) return;

        const rowStream = $transcriptOptsObj.$data.rowStreams['/metadata/' +  $datasetsSelect.id + '/transcripts/' + $transcriptSelect.name]
        const categories = rowStream.attrs.categories;
        const expressionSub = rowStream.current.subscribe(expression => {
            if(expression) set({...$transcriptOptsObj, expression, categories})
        })
        return () => expressionSub()
    })

    const plotlyArgs = derived([expressionDataObj, transcriptSelect, scaleSelect], ([$expressionDataObj, $transcriptSelect, $scaleSelect], set) => {
        if(!$expressionDataObj) set(getPlotEmpty('No data'));
        else if($expressionDataObj.expression.loading) set(getPlotEmpty('Loading'));
        else {
            // Prevent invalid combinations during updates
            const [ds, ts] = $transcriptSelect.id.split('|', 2)
            if(ds !== $expressionDataObj.$datasetsSelect.id) return

            const headingsX = $expressionDataObj.categories
            const headingsY = $expressionDataObj.expression.data.stringValues
            let values = $expressionDataObj.expression.data.floatValues

            if($scaleSelect.id === 'Log e') values = values.map(v => Math.log(v + 0.05))
            if($scaleSelect.id === 'Log 10') values = values.map(v => Math.log10(v + 0.05))

            values = headingsY.map((_, i) => values.slice(i*headingsX.length, (i+1)*headingsX.length))

            const combinedHeading = heading + ` - ${ds} (${headingsY.length} Transcripts)`;
            set({
                plotData: [{
                    z: values,
                    x: headingsX,
                    y: headingsY,
                    type: 'heatmap',
                    hoverongaps: false,
                    xgap: 0.5,
                    ygap: 0.5,
                    colorscale: [[-20, 'rgb(0,0,255)'], [20, 'rgb(255,0,0)']]
                }],
                layout: { 
                    height: Math.max(350, 30 * headingsY.length),
                    title: {
                        text: combinedHeading,
                        font: {
                            family: "Times New Roman",
                            size: 20
                        },
                    },
                    margin: {
                        l: 150,
                        r: 0,
                        b: 100,
                        t: 100,
                        pad: 4
                    },
                    xaxis: {
                        linecolor: 'black',
                        linewidth: 1,
                        mirror: true,
                    },
                    yaxis: {
                        linecolor: 'black',
                        linewidth: 1,
                        mirror: true,
                    },
                    legend: {
                        x: 1,
                        y: 0.5
                    }
                },
                config: { responsive: false },
                downloadCSV: getTablDownloader(combinedHeading, headingsX, headingsY, values)
            });
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
            <Dropdown title='Transcripts' selected={transcriptSelect} groups={$transcriptOptsObj.transcriptOpts}/>
            <Dropdown title='Scale' selected={scaleSelect} groups={scaleOpts}/>
        </div>
    </span>
</Plot>