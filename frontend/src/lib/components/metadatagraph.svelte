<script>
    import Dropdown from '../components/dropdown.svelte';
    import Plot from '../components/plot.svelte';
    import { page } from '$app/stores';
    import { Label, Input } from 'flowbite-svelte';

    import { writable, derived, get } from "svelte/store";
    import { getPlotEmpty, getPlotDistribution, getPlotScatter, getPlotBar } from '../utils/plot'

    import { getContext, onMount, tick } from "svelte";
    
    import { createPlotlyArgsFromMetadataOptions, SupportedCategoricalPlotTypes, SupportedLogTypes } from '$lib/utils/create';
    
    export let currentRow;
    export let filteredStore;
    export let heading;
    export let allowedPlotTypes = ["Violin", "Box", "Bar"];
    export let allowSecondMetadataSelect = true;
    
    const { readers } = getContext('core')
    const { colorWay, groupColorWay, colorPrimary, alwaysApplyColorWay } = getContext('displaySettings')

    let datasetsSelect = writable();
    let matrixSelect = writable();
    let metadataSelect1 = writable();
    let metadataSelect2 = writable();
    let showLoading = writable(true);

    onMount(() => { setTimeout(() => showLoading.set(false), 1) });
    
    const plotTypeOpts = new Map([['', SupportedCategoricalPlotTypes.filter(v => allowedPlotTypes.includes(v))]])
    let plotType = writable(plotTypeOpts.values().next().value[0]);

    let scaleSelect = writable('Log 2');
    const scaleOpts = new Map([['', SupportedLogTypes]])

    let expressionLinearThreshold = writable(0);

    let customSelect = writable()
    let customSelectName = 'Filter'

    function setExpressionVal(e) {
        let newVal = parseInt(e.target.value);
        if (isNaN(newVal)) newVal = 0;
        expressionLinearThreshold.set(newVal);
    }
    
    const datasetOptsObj = derived([readers, filteredStore, showLoading], ([$readers, $filteredStore, $showLoading], set) => {
        if($showLoading || !$readers || !$filteredStore) return;
        let datasetOptStrs = $filteredStore.datasetIndicesResults.map(col_i => $filteredStore.headings[col_i]);
        const datasetOptVals = datasetOptStrs.filter(ds => $readers[ds] !== undefined)
        const datasetsOpts = new Map([['', datasetOptVals]]);
        datasetsSelect.set(datasetOptVals[0]);
        set({datasetsOpts});
    });

    const matrixAndMetadataOptsObj = derived([readers, datasetsSelect], ([$readers, $datasetsSelect], set) => {
        if(!$datasetsSelect) return;
        const reader = $readers[$datasetsSelect];
        const matrixOptVals = reader.matrixNames;
        const matrixOpts = new Map([['', matrixOptVals]]);
        const metadataOptVals1 = reader.order;
        const metadataOptVals2 = reader.order.filter(v => (typeof reader.getColumn(v).values[0]) == 'string')
        const customOptVals = reader.customFilterCategory ? reader.customFilterCategory : []
        const customOpts = new Map([['', customOptVals]])
        customSelectName = reader.customFilterName

        function opstToGroups(opts, type) {
            const ret = new Map();
            if(type) {
                for(let i=0; i<opts.length; ++i) {
                    const arr = ret.get(type[i]) || [];
                    arr.push(opts[i]);
                    ret.set(type[i], arr);
                }
            } else {
                ret.set('', opts)
            }
            return ret
        }

        const metadataOpts1 = opstToGroups(metadataOptVals1, reader.type)
        const metadataOpts2 = opstToGroups(metadataOptVals2, reader.type)

        // Attempt to keep selected metadata and region filter if equivalent found
        metadataSelect1.update(current => metadataOptVals1.includes(current) ? current : metadataOptVals1[Math.max(0, reader.customDefaultColumn || 0)]);
        metadataSelect2.update(current => metadataOptVals2.includes(current) ? current : undefined);
        customSelect.update(current => customOptVals.includes(current) ? current : undefined);
        
        matrixSelect.set(matrixOptVals[0]);
        set({metadataOpts1, metadataOpts2, matrixOpts, customOpts})
    })

    const expressionDataObj = derived([readers, datasetsSelect, matrixSelect], ([$readers, $datasetsSelect, $matrixSelect], set) => {
        if(!$datasetsSelect || !$matrixSelect) return;
        const reader = $readers[$datasetsSelect];
        const expressionStore = reader.getMatrixStore['/metadata/' +  $datasetsSelect + '/matrices/' + $matrixSelect];
        return expressionStore.current.subscribe(set);
    })
    
    const pvalueDataObj = derived([currentRow, readers, datasetsSelect, matrixSelect], ([$currentRow, $readers, $datasetsSelect, $matrixSelect], set) => {
        if(!$datasetsSelect || !$matrixSelect) return;
        const reader = $readers[$datasetsSelect];
        const pvaluesStore = reader.getMatrixStore['/metadata/' +  $datasetsSelect + '/matrices/' + $matrixSelect + "_pvalues"];
        if (pvaluesStore !== undefined) {
            return pvaluesStore.current.subscribe(set);
        } else {
            set({data: undefined, row: $currentRow});  // N.B. Custom datasets do not have computed pvalues
        }
    })

    const plotlyArgs = derived([currentRow, readers, expressionDataObj, pvalueDataObj, datasetsSelect, matrixSelect, metadataSelect1, metadataSelect2, plotType, expressionLinearThreshold, scaleSelect, customSelect, colorWay, groupColorWay, colorPrimary, alwaysApplyColorWay], 
                            ([$currentRow, $readers, $expressionDataObj, $pvalueDataObj, $datasetsSelect, $matrixSelect, $metadataSelect1, $metadataSelect2, $plotType, $expressionLinearThreshold, $scaleSelect, $customSelect, $colorWay, $groupColorWay, $colorPrimary, $alwaysApplyColorWay], set) => {
        if (!$metadataSelect1 || $expressionDataObj?.row !== $currentRow || $pvalueDataObj?.row !== $currentRow) {
            
            console.log($metadataSelect1, $expressionDataObj, $pvalueDataObj, $currentRow)
            set(getPlotEmpty((!$expressionDataObj || $expressionDataObj?.loading || $pvalueDataObj?.loading) ? 'Loading...' : 'Not in dataset'))
        } else {
            const pvalueData = $pvalueDataObj?.data;
            const expressionData = $expressionDataObj.data;
            const reader = $readers[$datasetsSelect];
            set(createPlotlyArgsFromMetadataOptions(heading, reader, expressionData, pvalueData, $datasetsSelect, $matrixSelect, $metadataSelect1, $metadataSelect2, $plotType, $expressionLinearThreshold, $scaleSelect, $customSelect, $colorWay, $groupColorWay, $colorPrimary, $alwaysApplyColorWay));
        }
    });
</script>

<Plot plotlyArgs={plotlyArgs} controlsEnabled={datasetOptsObj}>
    <svelte:fragment slot="title">
        <i class='fas fa-gears'/> Metadata
    </svelte:fragment>
    
    <span slot="controls">
        <div class='w-48 flex flex-col items-stretch gap-3'>
            <Dropdown title='Dataset' selected={datasetsSelect} groups={$datasetOptsObj.datasetsOpts}/>
            
            {#if customSelectName}
                <Dropdown title={customSelectName} selected={customSelect} groups={$matrixAndMetadataOptsObj.customOpts} optional={true}/>
            {/if}
            {#if $matrixAndMetadataOptsObj?.matrixOpts.get('').length > 1}
                <Dropdown title='Matrix' selected={matrixSelect} groups={$matrixAndMetadataOptsObj.matrixOpts}/>
            {/if}
            <Dropdown title='Metadata 1' selected={metadataSelect1} groups={$matrixAndMetadataOptsObj.metadataOpts1}/>

            {#if allowSecondMetadataSelect}
            <Dropdown title='Metadata 2' selected={metadataSelect2} groups={$matrixAndMetadataOptsObj.metadataOpts2} optional={true}/>
            {/if}

            {#if allowedPlotTypes.length > 1}
            <Dropdown title='Categorical Plot Type' selected={plotType} groups={plotTypeOpts}/>
            {/if}

            {#if $plotType === "Bar"}
            <div class="space-y-2 w-52">
                <Label>
                    <span class="p-2 text-gray-500">Expression Threshold (Linear)</span>
                    <Input class="text-center"
                        on:blur={(e) => setExpressionVal(e) } 
                        on:keydown={(e) => (e.key === 'Enter') && setExpressionVal(e) }
                        value={$expressionLinearThreshold} required/>
                </Label>
            </div>
            {:else}
                <Dropdown title='Scale' selected={scaleSelect} groups={scaleOpts}/>
            {/if}
        </div>
    </span>
</Plot>
