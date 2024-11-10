<script>
    import Dropdown from '../components/dropdown.svelte';
    import Plot from '../components/plot.svelte';

    import { getZipped } from '../utils/plot'
    
    import { writable, derived } from "svelte/store";
    import { getPlotEmpty, getPlotViolinBasic, getPlotScatter } from '../utils/plot';
    import { withoutNulls } from '../utils/hdf5';

    import { getContext } from "svelte";
    import { createMetadataStore } from '../stores/metadata'
    
    import { LOG_OFFSET } from '../utils/math'

    export let filteredStore;
    export let heading;

    const core = getContext('core')
    const { colorWay } = getContext('palettes')
    const metadataStore = createMetadataStore(core)

    let datasetsSelect = writable();
    let matrixSelect = writable();
    let metadataSelect1 = writable();
    let metadataSelect2 = writable();

    let scaleSelect = writable({id: 'Linear', name: 'Linear'});
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

    const plotlyArgs = derived([expressionDataObj, metadataSelect1, metadataSelect2, scaleSelect, customSelect, colorWay], ([$expressionDataObj, $metadataSelect1, $metadataSelect2, $scaleSelect, $customSelect, $colorWay], set) => {
        if(!$expressionDataObj || !$metadataSelect1) {
            return
        } else if (!$expressionDataObj.expression.data) {
            set(getPlotEmpty($expressionDataObj.expression.loading ? 'Loading...' : 'Not in dataset'))
        } else {
            // Prevent invalid combinations during updates
            const [ds1, ms1] = $metadataSelect1.id.split('|', 2)
            const [ds2, ms2] = ($metadataSelect2?.id || '|').split('|', 2)
            const [ds3, cs] = ($customSelect?.id || '|').split('|', 2)

            if([ds1, ds2, ds3].some(ds => ds && ds !== $expressionDataObj.$datasetsSelect.id)) return
            
            const reader = $expressionDataObj.$metadataStore.readers[ds1];
            const x = withoutNulls(reader.getColumn(ms1).values)
            const z = ms2 && withoutNulls(reader.getColumn(ms2).values)
            
            const names = reader.sampleNames;
            let y = $expressionDataObj.expression.data.values;
            
            const orderX = reader.getColumn(ms1).attrs.order
            const orderZ = ms2 && reader.getColumn(ms2).attrs.order
            
            const groupSizesX = reader.getColumn(ms1).attrs.groupSizes
            const groupLabelsX = reader.getColumn(ms1).attrs.groupLabels

            const headingX = ms1;
            let headingY = $expressionDataObj.$matrixSelect.name;
            const headingZ = ms2;

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
            
            if((typeof data[0].x) == 'string' || data[0].x instanceof String) {
                set(getPlotViolinBasic(headingMain, data, headingX, headingY, headingZ, orderX, orderZ, groupLabelsX, groupSizesX, $colorWay))
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
