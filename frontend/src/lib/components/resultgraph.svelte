<script>
    import Dropdown from '../components/dropdown.svelte';
    import Plot from '../components/plot.svelte';
    import { writable } from "@square/svelte-store";
   
    export let filteredStore;

    let datasetsAll;

    let datasetsSelect1 = writable();
    let datasetsSelect2 = writable();

    let plotlyArgs = writable(undefined);

    // Initial data parse
    filteredStore.subscribe(fs => {
        if(fs) {
            datasetsAll = new Map([['', fs.datasetIndicesResults.map(col_i => fs.headings[col_i]).map(h => ({id: h, name: h}))]])
            datasetsSelect1.set(datasetsAll.get('')[0]);
            datasetsSelect2.set(datasetsAll.get('')[1]);
        }
    });

    $: {
        if($filteredStore && $datasetsSelect1 && $datasetsSelect2) {
            const inds = [$datasetsSelect1.id, $datasetsSelect2.id].map(h => $filteredStore.headings.indexOf(h));
            const [x, y] = inds.map(col_i => $filteredStore.results.map(row_i => $filteredStore.columns[col_i][row_i]));
            const filteredNames = $filteredStore.results.map(row_i => $filteredStore.columns[1][row_i]);
            
            plotlyArgs.set({
                plotData: [
                    {
                        mode: 'markers',
                        type: 'scattergl',
                        name: 'all',
                        x: $filteredStore.columns[inds[0]],
                        y: $filteredStore.columns[inds[1]],
                        hoverinfo: 'skip',
                        marker : {color: 'rgb(219, 219, 219)'}
                    },
                    {
                        mode: 'markers',
                        type: 'scattergl',
                        name: '',
                        x: x,
                        y: y,
                        marker : {color: 'rgb(196, 89, 59)'},
                        text: filteredNames
                    }
                ]
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
