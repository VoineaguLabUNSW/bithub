<script>
    import Dropdown from '../components/dropdown.svelte';
    import Plot from '../components/plot.svelte';
    import { writable } from "@square/svelte-store";
    import { getContext } from "svelte";
    import { derived } from 'svelte/store';
    import { getPlotEmpty, getTableDownloader } from '../utils/plot';

    export let filteredStore;
    export let heading;

    const { data } = getContext('core');
    const { colorRange } = getContext('palettes')

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

    const plotlyArgs = derived([expressionDataObj, transcriptSelect, scaleSelect, colorRange], ([$expressionDataObj, $transcriptSelect, $scaleSelect, $colorRange], set) => {
        if(!$expressionDataObj) set(getPlotEmpty('No data'));
        else if($expressionDataObj.expression.loading) set(getPlotEmpty('Loading'));
        else {
            // Prevent invalid combinations during updates
            const [ds, ts] = $transcriptSelect.id.split('|', 2)
            if(ds !== $expressionDataObj.$datasetsSelect.id) return

            const headingsX = $expressionDataObj.categories
            const headingsY = $expressionDataObj.expression.data.stringValues
            let values = $expressionDataObj.expression.data.floatValues

            let combinedHeading = heading + ` - ${ds} (${headingsY.length} Transcripts)`;

            let range = [0, 20]
            if($scaleSelect.id !== 'Linear') {
                range = [-5, 5]
                combinedHeading += ` - ${$scaleSelect.id}`
                if($scaleSelect.id === 'Log e') values = values.map(v => Math.log(v + 0.05))
                if($scaleSelect.id === 'Log 10') values = values.map(v => Math.log10(v + 0.05))
            }

            values = headingsY.map((_, i) => values.slice(i*headingsX.length, (i+1)*headingsX.length))

            set({
                plotData: [{
                    z: values,
                    x: headingsX,
                    y: headingsY,
                    type: 'heatmap',
                    hoverongaps: false,
                    xgap: 0.5,
                    ygap: 0.5,
                    colorscale: [[0, $colorRange[0]], [0.5, $colorRange[1]], [1, $colorRange[2]]],
                    zmin: range[0],
                    zmax: range[1]
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
                downloadCSV: getTableDownloader(combinedHeading, headingsX, headingsY, values)
            });
        }
    })
</script>

<Plot plotlyArgs={plotlyArgs}>
    <svelte:fragment slot="title">
        <i class='fas fa-gears'/> Dataset
    </svelte:fragment>
    <span slot="controls">
        <div class='w-48 flex flex-col items-stretch gap-3'>
            <Dropdown title='Dataset' selected={datasetsSelect} groups={$datasetOptsObj.datasetsOpts}/>
            <Dropdown title='Transcripts' selected={transcriptSelect} groups={$transcriptOptsObj?.transcriptOpts}/>
            <Dropdown title='Scale' selected={scaleSelect} groups={scaleOpts}/>
        </div>
    </span>
</Plot>