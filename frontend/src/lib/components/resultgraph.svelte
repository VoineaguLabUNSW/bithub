<script>
    import { getPlotEmpty, getColumnDownloader, getZipped, getWithNA } from '../utils/plot';
    import Dropdown from '../components/dropdown.svelte';
    import Plot from '../components/plot.svelte';
    import { writable, get } from "svelte/store";
    import { primary } from '../utils/colors'
   
    export let filteredStore;
    export let heading;

    let datasetsAll;

    let datasetsSelect1 = writable();
    let datasetsSelect2 = writable();

    let plotlyArgs = writable(undefined);

    // Initial data parse
    filteredStore.subscribe(fs => {
        if(fs) {
            const datasetAvail = fs.datasetIndicesResults.map(col_i => fs.headings[col_i]);
            const datasetOptVals =  datasetAvail.map(h => ({id: h, name: h}))
            datasetsAll = new Map([['', datasetOptVals]])
            if(!datasetAvail.includes(get(datasetsSelect1)?.id)) datasetsSelect1.set(datasetOptVals[0]);
            if(!datasetAvail.includes(get(datasetsSelect2)?.id)) datasetsSelect2.set(datasetOptVals[1]);
        }
    });

    $: {
        if(!$filteredStore || !$datasetsSelect1 || !$datasetsSelect2) {
            plotlyArgs.set(getPlotEmpty('No results'))
        } else {
            const inds = [$datasetsSelect1.id, $datasetsSelect2.id].map(h => $filteredStore.headings.indexOf(h));
            const [x, y] = inds.map(col_i => $filteredStore.results.map(row_i => $filteredStore.columns[col_i][row_i]));
            const filteredNames = $filteredStore.results.map(row_i => $filteredStore.columns[1][row_i]);

            let extraMarkerArgs = {}
            if(filteredNames.length == 1) {
                extraMarkerArgs = {
                    line: { color: 'white', width: 1 },
                    size: 15
                }
            }
            const xName = $datasetsSelect1.id;
            const yName = $datasetsSelect2.id;
            
            plotlyArgs.set({
                plotData: [{
                        mode: 'markers',
                        type: 'scattergl',
                        x: $filteredStore.columns[inds[0]],
                        y: $filteredStore.columns[inds[1]],
                        hoverinfo: 'skip',
                        marker : {color: 'lightgray'}
                    },{
                        mode: 'markers',
                        type: 'scattergl',
                        name: '',
                        x: x,
                        y: y,
                        marker : {color: primary[600], ...extraMarkerArgs},
                        text: filteredNames
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
                            text: $datasetsSelect1.id,
                            font: { family: 'Times New Roman', size: 18, color: '#7f7f7f' }
                        },
                    },
                    yaxis: {
                        title: {
                            text: $datasetsSelect2.id,
                            font: { family: 'Times New Roman', size: 18, color: '#7f7f7f' }
                        }
                    },
                },
                downloadCSV: getColumnDownloader(heading, getZipped({x: getWithNA(x), y: getWithNA(y), name: filteredNames}), xName, yName)
            });
        }  
    }
</script>

<Plot plotlyArgs={plotlyArgs}>
    <span slot="controls">
        <div class="flex justify-between">
            <h5 id="drawer-label" class="inline-flex items-center mb-4 text-base font-semibold text-gray-500 dark:text-gray-400">
                <i class='fas fa-gears m-2'/>Datasets
            </h5>
        </div>
        <p class="mb-6 text-sm text-gray-500 dark:text-gray-400">
            Select from different datasets to compare z-scores for any number of search results.
        </p>
        <div class='w-48 flex flex-col items-stretch gap-3'>
            <Dropdown title='Dataset 1' placeholder='No Datasets' selected={datasetsSelect1} groups={datasetsAll}/>
            <Dropdown title='Dataset 2' placeholder='No Datasets' selected={datasetsSelect2} groups={datasetsAll}/>
        </div>
    </span>
</Plot>
