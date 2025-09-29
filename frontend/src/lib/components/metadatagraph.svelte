<script>
    import Dropdown from '../components/dropdown.svelte';
    import Plot from '../components/plot.svelte';
    import { page } from '$app/stores';

    import { getZipped } from '../utils/plot'
    
    import { writable, derived } from "svelte/store";
    import { getPlotEmpty, getPlotDistribution, getPlotScatter } from '../utils/plot'
    import { withoutNulls } from '../utils/hdf5';

    import { getContext } from "svelte";
    import { createMetadataStore } from '../stores/metadata'
    
    import { LOG_OFFSET } from '../utils/math'

    export let filteredStore;
    export let heading;
    export let type;

    const core = getContext('core')
    const { colorWay } = getContext('displaySettings')
    const metadataStore = createMetadataStore(core)

    let datasetsSelect = writable();
    let matrixSelect = writable();
    let metadataSelect1 = writable();
    let metadataSelect2 = writable();

    let scaleSelect = writable({id: 'Log 2', name: 'Log 2'});
    const scaleOpts = new Map([['', ['Linear', 'Log e', 'Log 2', 'Log 10'].map(l => ({id: l, name: l}))]])

    let customSelect = writable()
    let customSelectName = 'Filter'
    
    const datasetOptsObj = derived([metadataStore, filteredStore], ([$metadataStore, $filteredStore], set) => {
        if(!$metadataStore || !$filteredStore) return;
        let datasetOptStrs = $filteredStore.datasetIndicesResults.map(col_i => $filteredStore.headings[col_i]);
        datasetOptStrs = datasetOptStrs.filter(ds => $metadataStore.readers[ds] !== undefined)
        const datasetOptVals = datasetOptStrs.map(h => ({id: h, name: h}));
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
        const customOptVals = reader.customFilterCategory ? reader.customFilterCategory.map((o, i) => ({i, id: $datasetsSelect.id + '|' + o, name: o})) : []
        const customOpts = new Map([['', customOptVals]])
        customSelectName = reader.customFilterName

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
        customSelect.set(undefined)
        matrixSelect.set(matrixOptVals[0]);
        set({...$datasetOptsObj, $datasetsSelect, metadataOpts1, metadataOpts2, matrixOpts, customOpts})
    })

    const expressionDataObj = derived([matrixOptsObj, matrixSelect], ([$matrixOptsObj, $matrixSelect], set) => {
        if(!$matrixOptsObj || !$matrixSelect) return;
        const reader = $matrixOptsObj.$metadataStore.readers[$datasetsSelect.id];
        const expressionSub = reader.getMatrixStore['/metadata/' +  $datasetsSelect.id + '/matrices/' + $matrixSelect.id].current.subscribe(expression => {
            if(expression) set({...$matrixOptsObj, expression: expression, $matrixSelect})
        })
        return () => expressionSub()
    })
    
    const pvalueDataObj = derived([matrixOptsObj, matrixSelect], ([$matrixOptsObj, $matrixSelect], set) => {
        if(!$matrixOptsObj || !$matrixSelect) return;
        const reader = $matrixOptsObj.$metadataStore.readers[$datasetsSelect.id];
        const expressionSub = reader.getMatrixStore['/metadata/' +  $datasetsSelect.id + '/matrices/' + $matrixSelect.id + "_pvalues"].current.subscribe(pvalues => {
            if(pvalues) set({...$matrixOptsObj, pvalues: pvalues, $matrixSelect})
        })
        return () => expressionSub()
    })

    const plotlyArgs = derived([expressionDataObj, pvalueDataObj, metadataSelect1, metadataSelect2, scaleSelect, customSelect, colorWay], ([$expressionDataObj, $pvalueDataObj, $metadataSelect1, $metadataSelect2, $scaleSelect, $customSelect, $colorWay], set) => {
        if(!$expressionDataObj || !pvalueDataObj || !$metadataSelect1) {
            return
        } else if (!$expressionDataObj.expression.data) {
            set(getPlotEmpty(($expressionDataObj.expression.loading || $pvalueDataObj.pvalues.loading) ? 'Loading...' : 'Not in dataset'))
        } else {
            // Prevent invalid combinations during updates
            const [ds1, ms1] = $metadataSelect1.id.split('|', 2)
            const [ds2, ms2] = ($metadataSelect2?.id || '|').split('|', 2)
            const [ds3, cs] = ($customSelect?.id || '|').split('|', 2)

            if([ds1, ds2, ds3].some(ds => ds && (ds !== $expressionDataObj.$datasetsSelect.id || ds !== $pvalueDataObj.$datasetsSelect.id))) return
            
            const reader = $expressionDataObj.$metadataStore.readers[ds1];
            let x = withoutNulls(reader.getColumn(ms1).values)
            const z = ms2 && withoutNulls(reader.getColumn(ms2).values)
            
            const names = reader.sampleNames;
            let y = $expressionDataObj.expression.data.values;
            
            const orderX = reader.getColumn(ms1).attrs.order
            const orderZ = ms2 && reader.getColumn(ms2).attrs.order
            
            const groupSizesX = reader.getColumn(ms1).attrs.groupSizes
            const groupLabelsX = reader.getColumn(ms1).attrs.groupLabels

            const headingX = ms2 ? ms1 : `${ms1} (p = ${$pvalueDataObj.pvalues.data.values[reader.order.indexOf(ms1)].toFixed(2)})`
            let headingY = $expressionDataObj.$matrixSelect.name;
            const headingZ = ms2;
            
            // Calculate % expressing/nonzero and add to x labels if required
            const isCategorical = (typeof x[0]) == 'string' || x[0] instanceof String
            if (isCategorical) {
                let zeroXCounts = {}
                x.forEach((v, i) => {
                    let curr = zeroXCounts[v];
                    if (curr === undefined) curr = zeroXCounts[v] = [0, 0, 0, undefined];
                    curr[0]++;
                    if (y[i] !== 0) curr[1]++; // Track nonzero for each category
                    if (y[i] >= 1) curr[2]++; // Track greater than 1 for each category
                });
                for (const [v, curr] of Object.entries(zeroXCounts)) {
                    curr[3] = ((curr[1] === curr[0]) || !curr[2]) ? v : `${v} (${(curr[1]/curr[0]*100).toFixed(2)}% expr)`                
                }
                x = x.map(v => zeroXCounts[v][3])
            }
            
            if($scaleSelect.id === 'Log e') y = y.map(v => Math.log(v + LOG_OFFSET))
            if($scaleSelect.id === 'Log 2') y = y.map(v => Math.log2(v + LOG_OFFSET))
            if($scaleSelect.id === 'Log 10') y = y.map(v => Math.log10(v + LOG_OFFSET))

            let data = getZipped({x, y, z, name: names})
            if(cs) {
                const csColumn = withoutNulls(reader.getColumn(reader.customFilterColumn).values)
                data = data.filter((d, i) => csColumn[i] == cs)
            }

            const headingMain = `${heading} - ${ds1}`
            if($scaleSelect.id != 'Linear') headingY = `${headingY} (${$scaleSelect.id})`
            
            if(isCategorical) {
                set(getPlotDistribution(headingMain, data, headingX, headingY, headingZ, orderX, orderZ, groupLabelsX, groupSizesX, $colorWay, $page.url.searchParams.get('plotType') || type, ms1 == reader.customFilterColumn))
            } else {
                set(getPlotScatter(headingMain, data, headingX, headingY, headingZ, orderZ, $colorWay))   
            }
        }
    });
</script>

<Plot plotlyArgs={plotlyArgs}>
    <svelte:fragment slot="title">
        <i class='fas fa-gears'/> Metadata
    </svelte:fragment>
    <span slot="controls">
        <div class='w-48 flex flex-col items-stretch gap-3'>
            <Dropdown title='Dataset' selected={datasetsSelect} groups={$datasetOptsObj.datasetsOpts}/>
            
            {#if customSelectName}
                <Dropdown title={customSelectName} selected={customSelect} groups={$matrixOptsObj.customOpts} optional={true}/>
            {/if}
            {#if $matrixOptsObj?.matrixOpts.get('').length > 1}
                <Dropdown title='Matrix' selected={matrixSelect} groups={$matrixOptsObj.matrixOpts}/>
            {/if}
            <Dropdown title='Metadata 1' selected={metadataSelect1} groups={$matrixOptsObj.metadataOpts1}/>
            <Dropdown title='Metadata 2' selected={metadataSelect2} groups={$matrixOptsObj.metadataOpts2} optional={true}/>
            <Dropdown title='Scale' selected={scaleSelect} groups={scaleOpts}/>
        </div>
    </span>
</Plot>
