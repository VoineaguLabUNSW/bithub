<script>
    import Dropdown from '../components/dropdown.svelte';
    import Plot from '../components/plot.svelte';
    import { writable, get } from "@square/svelte-store";
    import { getContext, onMount } from "svelte";
    import { createMetadataStore } from '../stores/metadata'
    import { derived } from 'svelte/store';
    import { getPlotEmpty } from '../utils/plot';

    export let filteredStore;
    export const description = 'This is a panel'

    let datasetsSelect = writable();
    let matrixSelect = writable();
    let metadataSelect = writable();

    const core = getContext('core');
    const metadataStore = createMetadataStore(core)
    
    const datasetOptsObj = derived([metadataStore, filteredStore], ([$metadataStore, $filteredStore], set) => {
        if(!$metadataStore || !$filteredStore) return;
        const datasetOptVals = $filteredStore.datasetIndicesResults.map(col_i => $filteredStore.headings[col_i]).map(h => ({id: h, name: h}));
        const datasetsOpts = new Map([['', datasetOptVals]]);
        datasetsSelect.set(datasetOptVals[0]);
        set({$metadataStore, datasetsOpts});
        
    });

    const matrixOptsObj = derived([datasetOptsObj, datasetsSelect], ([$datasetOptsObj, $datasetsSelect], set) => {
        if(!$datasetOptsObj || !$datasetsSelect) return;
        const reader = $datasetOptsObj.$metadataStore.readers[$datasetsSelect.id];
        const matrixOptVals = reader.matrixNames.map(m => ({id: m, name: m}));
        const matrixOpts = new Map([['', matrixOptVals]]);
        const metadataOptVals = reader.order.map(o => ({id: $datasetsSelect.id + '|' + o, name: o}))
        const metadataOpts = new Map();
        if(reader.type) {
            for(let i=0; i<reader.type.length; ++i) {
                const arr = metadataOpts.get(reader.type[i]) || [];
                arr.push(metadataOptVals[i]);
                metadataOpts.set(reader.type[i], arr);
            }
        } else {
            metadataOpts.set('', metadataOptVals)
        }
        metadataSelect.set(metadataOptVals[0]);
        matrixSelect.set(matrixOptVals[0]);
        set({...$datasetOptsObj, $datasetsSelect, metadataOpts, matrixOpts})
    })

    const expressionDataObj = derived([matrixOptsObj, matrixSelect], ([$matrixOptsObj, $matrixSelect], set) => {
        if(!$matrixOptsObj || !$matrixSelect) return;
        const reader = $matrixOptsObj.$metadataStore.readers[$datasetsSelect.id];
        const expressionSub = reader.getMatrixStore[$datasetsSelect.id + ':' + $matrixSelect.id].current.subscribe(expression => {
            if(expression) set({...$matrixOptsObj, expression})
        })
        return () => expressionSub()
    })

    const plotlyArgs = derived([expressionDataObj, metadataSelect], ([$expressionDataObj, $metadataSelect], set) => {
        if(!$expressionDataObj || !$metadataSelect) {
            return
        } else if (!$expressionDataObj.expression.data) {
            set(getPlotEmpty($expressionDataObj.expression.loading ? 'Loading...' : 'Not in dataset'))
        } else {
            const [ds, ms] = $metadataSelect.id.split('|', 2)
            if(ds !== $expressionDataObj.$datasetsSelect.id) return
            console.log($metadataSelect.id)
            const reader = $expressionDataObj.$metadataStore.readers[ds];
            const [x, y] = [reader.getColumn(ms).values, $expressionDataObj.expression.data];
            console.log(x, y)
            set({
                plotData: [
                    {
                        mode: 'markers',
                        type: 'scattergl',
                        name: 'all',
                        x: x,
                        y: y
                    }
            ]});
        }
    });
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
            <Dropdown title='Dataset' selected={datasetsSelect} groups={$datasetOptsObj.datasetsOpts}/>
            <Dropdown title='Matrix' selected={matrixSelect} groups={$matrixOptsObj.matrixOpts}/>
            <Dropdown title='Metadata' selected={metadataSelect} groups={$matrixOptsObj.metadataOpts}/>
        </div>
    </span>
</Plot>
