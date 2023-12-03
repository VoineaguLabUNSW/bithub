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
    let metadataSelect1 = writable();
    let metadataSelect2 = writable();

    let scaleSelect = writable({id: 'Linear', name: 'Linear'});
    const scaleOpts = new Map([['', ['Linear', 'Log e', 'Log 10'].map(l => ({id: l, name: l}))]])

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
        const metadataOptVals1 = reader.order.map((o, i) => ({i, id: $datasetsSelect.id + '|' + o, name: o}))
        const metadataOptVals2 = metadataOptVals1.filter(v => (typeof reader.getColumn(v.name).values[0]) == 'string')
        
        function opstToGroups(opts, type) {
            const ret = new Map();
            if(type) {
                for(let o of opts) {
                    const arr = ret.get(reader.type[o.i]) || [];
                    arr.push(o);
                    ret.set(reader.type[o.i], arr);
                }
            } else {
                ret.set('', opts)
            }
            return ret
        }

        const metadataOpts1 = opstToGroups(metadataOptVals1, reader.type)
        const metadataOpts2 = opstToGroups(metadataOptVals2, reader.type)
        
        metadataSelect1.set(metadataOptVals1[0]);
        metadataSelect2.set(undefined)
        matrixSelect.set(matrixOptVals[0]);

        console.log(metadataOpts2)

        set({...$datasetOptsObj, $datasetsSelect, metadataOpts1, metadataOpts2, matrixOpts})
    })

    const expressionDataObj = derived([matrixOptsObj, matrixSelect], ([$matrixOptsObj, $matrixSelect], set) => {
        if(!$matrixOptsObj || !$matrixSelect) return;
        const reader = $matrixOptsObj.$metadataStore.readers[$datasetsSelect.id];
        const expressionSub = reader.getMatrixStore['/metadata/' +  $datasetsSelect.id + '/matrices/' + $matrixSelect.id].current.subscribe(expression => {
            if(expression) set({...$matrixOptsObj, expression: expression})
        })
        return () => expressionSub()
    })

    const plotlyArgs = derived([expressionDataObj, metadataSelect1, metadataSelect2, scaleSelect], ([$expressionDataObj, $metadataSelect1, $metadataSelect2, $scaleSelect], set) => {
        console.log($expressionDataObj.expression)
        if(!$expressionDataObj || !$metadataSelect1) {
            return
        } else if (!$expressionDataObj.expression.data) {
            set(getPlotEmpty($expressionDataObj.expression.loading ? 'Loading...' : 'Not in dataset'))
        } else {
            // Prevent invalid combinations during updates
            const [ds, ms] = $metadataSelect1.id.split('|', 2)
            if(ds !== $expressionDataObj.$datasetsSelect.id) return

            const reader = $expressionDataObj.$metadataStore.readers[ds];
            let [x, y] = [reader.getColumn(ms).values, $expressionDataObj.expression.data.values];

            if($scaleSelect.id === 'Log e') y = y.map(v => Math.log(v))
            if($scaleSelect.id === 'Log 10') y = y.map(v => Math.log10(v))
            
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
                <i class='fas fa-gears m-2'/>Metadata
            </h5>
        </div>
        <div class='w-48 flex flex-col items-stretch gap-3'>
            <Dropdown title='Dataset' selected={datasetsSelect} groups={$datasetOptsObj.datasetsOpts}/>
            {#if $matrixOptsObj?.matrixOpts.get('').length > 1}
                <Dropdown title='Matrix' selected={matrixSelect} groups={$matrixOptsObj.matrixOpts}/>
            {/if}
            <Dropdown title='Metadata 1' selected={metadataSelect1} groups={$matrixOptsObj.metadataOpts1}/>
            <Dropdown title='Metadata 2' selected={metadataSelect2} groups={$matrixOptsObj.metadataOpts2} optional={true}/>
            <Dropdown title='Scale' selected={scaleSelect} groups={scaleOpts}/>
        </div>
    </span>
</Plot>
