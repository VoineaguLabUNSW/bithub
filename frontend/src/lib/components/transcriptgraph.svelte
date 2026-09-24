<script>
    import Dropdown from '../components/dropdown.svelte';
    import Plot from '../components/plot.svelte';
    import { writable } from "@square/svelte-store";
    import { getContext } from "svelte";
    import { derived } from 'svelte/store';
    import { getPlotEmpty, getTableDownloader } from '../utils/plot';
    import {count, mean, sd, LOG_OFFSET} from '../utils/math';
    import { SupportedLogTypes } from '$lib/utils/create';

    export let currentRow;
    export let filteredStore;
    export let heading;

    const { data, readers } = getContext('core');
    const { colorRange } = getContext('displaySettings')

    let datasetsSelect = writable();
    let transcriptSelect = writable();
    
    let normalizationSelect = writable('None');
    const normalizationOpts = new Map([['', ['None', 'Z-Score (within transcript)', 'Z-Score (within category)']]])
    
    const datasetOptsObj = derived([data, filteredStore], ([$data, $filteredStore], set) => {
        if(!$data || !$filteredStore) return;
        const datasetOptVals = $filteredStore.datasetIndicesResults.map(col_i => $filteredStore.headings[col_i]);
        const datasetsOpts = new Map([['', datasetOptVals]]);
        datasetsSelect.set(datasetOptVals[0]);
        set({datasetsOpts});
    });

    const transcriptOptsObj = derived([data, datasetOptsObj, datasetsSelect], ([$data, $datasetOptsObj, $datasetsSelect], set) => {
        if(!$datasetOptsObj || !$datasetsSelect) return;
        const transcriptOptVals = $data.value.get('metadata/' + $datasetsSelect + '/transcripts').attrs.order
        const transcriptOpts = new Map([['', transcriptOptVals]]);
        transcriptSelect.set(transcriptOptVals[0]);
        set({transcriptOpts})
    });

    const expressionDataObj = derived([readers, datasetsSelect, transcriptSelect], 
                                    ([$readers, $datasetsSelect, $transcriptSelect], set) => {
        if(!$datasetsSelect || !$transcriptSelect) return;
        const reader = $readers[$datasetsSelect];
        const transcriptStore = reader.getMatrixStore['/metadata/' + $datasetsSelect + '/transcripts/' + $transcriptSelect]
        return transcriptStore.current.subscribe(set);
    })
    
    const plotlyArgs = derived([currentRow, data, expressionDataObj, datasetsSelect, transcriptSelect, normalizationSelect, colorRange], ([$currentRow, $data, $expressionDataObj, $datasetsSelect, $transcriptSelect, $normalizationSelect, $colorRange], set) => {
        if(!$expressionDataObj || $expressionDataObj.row !== $currentRow) set(getPlotEmpty('No data'));
        else if($expressionDataObj.loading) set(getPlotEmpty('Loading'));
        else {
            const headingsX = $data.rowStreams['/metadata/' +  $datasetsSelect + '/transcripts/' + $transcriptSelect].attrs.categories;
            const headingsY = $expressionDataObj.data.stringValues
            let values = $expressionDataObj.data.floatValues

            let combinedHeading = heading + ` - ${$datasetsSelect} (${headingsY.length} Transcripts)`;
            
            // Convert to 2D
            values = headingsY.map((_, i) => values.slice(i*headingsX.length, (i+1)*headingsX.length));

            // Transcript matrices are already log2-transformed upstream, so no scale
            let modifiers = ['Log 2'];
            
            if ($normalizationSelect != 'None') {
                modifiers.push($normalizationSelect);
                if ($normalizationSelect == 'Z-Score (within transcript)') {
                    for(let i=0; i<values.length; ++i) {
                        const groupVals = values[i];
                        const valsMean = mean(groupVals);
                        const valsSD = sd(groupVals, valsMean) || 0.0000000001;
                        values[i] = groupVals.map(x => (x - valsMean) / valsSD);
                    }
                } else {
                    for(let i=0; i<values[0].length; ++i) {
                        const groupVals = values.map((_, j) => values[j][i]);
                        const valsMean = mean(groupVals);
                        const valsSD = sd(groupVals, valsMean) || 0.0000000001;
                        for(let j=0; j<values.length; ++j) values[j][i] = ((values[j][i] - valsMean) / valsSD) 
                    }
                }
            }

            if (modifiers.length) combinedHeading += ` - ${modifiers.join("/")}`;

            const maxAbs = Math.max(...(values.flat().filter(v => !Number.isNaN(v)) || [0]));
            const range = maxAbs > 0 ? [-maxAbs, +maxAbs] : [-1, 1];
            const colorscale = [[0, $colorRange[0]], [0.5, $colorRange[1]], [1, $colorRange[2]]];

            set({
                plotData: [{
                    z: values,
                    x: headingsX,
                    y: headingsY,
                    type: 'heatmap',
                    hoverongaps: false,
                    xgap: 0.5,
                    ygap: 0.5,
                    colorscale: colorscale,
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
            <Dropdown title='Normalization' selected={normalizationSelect} groups={normalizationOpts}/>
        </div>
    </span>
</Plot>