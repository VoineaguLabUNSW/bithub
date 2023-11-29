<script>
    import Dropdown from '../components/dropdown.svelte'
    import Plot from '../components/plot.svelte'
    import { writable } from "@square/svelte-store";
   

    export let filteredStore;

    let datasetsAll;

    let datasetsSelect1 = writable('')
    let datasetsSelect2 = writable('')

    let plotlyArgs = writable(undefined)

    // Initial data parse
    filteredStore.subscribe(fs => {
        if(fs && !datasetsAll) {
            const { headingGroups } = fs
            datasetsAll = headingGroups.get('Datasets')
            datasetsSelect1.set(datasetsAll[0])
            datasetsSelect2.set(datasetsAll[1])
        }
    });

    $: {
        if($filteredStore && $datasetsSelect1 && $datasetsSelect2) {

            const inds = [$datasetsSelect1, $datasetsSelect2].map(h => $filteredStore.headings.indexOf(h))
            const cols = inds.map(i => $filteredStore.columns[i])
            const filteredInd = inds.map((col_i, d_i) => $filteredStore.results.map(row_i => cols[d_i][row_i]))
            const filteredNames = $filteredStore.results.map(row_i => $filteredStore.columns[1][row_i])
            
            plotlyArgs.set({
                plotData: [
                    {
                        mode: 'markers',
                        type: 'scattergl',
                        name: 'all',
                        x: cols[0],
                        y: cols[1],
                        hoverinfo: 'skip',
                        marker : {color: 'rgb(219, 219, 219)'}
                    },
                    {
                        mode: 'markers',
                        type: 'scattergl',
                        name: '',
                        x: filteredInd[0],
                        y: filteredInd[1],
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
            <Dropdown title='Dataset 1' selected={datasetsSelect1} groups={new Map([['', datasetsAll]])}/>
            <Dropdown title='Dataset 2' selected={datasetsSelect2} groups={new Map([['', datasetsAll]])}/>
        </div>
    </span>
</Plot>
