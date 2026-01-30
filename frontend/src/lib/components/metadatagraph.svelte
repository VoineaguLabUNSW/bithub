<script>
    import Dropdown from '../components/dropdown.svelte';
    import Plot from '../components/plot.svelte';
    import { page } from '$app/stores';
    import { Label, Input } from 'flowbite-svelte';

    import { getZipped } from '../utils/plot'
    
    import { writable, derived, get } from "svelte/store";
    import { getPlotEmpty, getPlotDistribution, getPlotScatter, getPlotBar } from '../utils/plot'
    import { withoutNulls } from '../utils/hdf5';

    import { getContext, onMount, tick } from "svelte";
    import { createMetadataStore } from '../stores/metadata'
    
    import { LOG_OFFSET } from '../utils/math'

    export let filteredStore;
    export let heading;
    export let allowedPlotTypes = ["Violin", "Box", "Bar"];
    export let allowSecondMetadataSelect = true;
    
    const core = getContext('core')
    const { colorWay, groupColorWay, colorPrimary, alwaysApplyColorWay } = getContext('displaySettings')
    const metadataStore = createMetadataStore(core)

    let datasetsSelect = writable();
    let matrixSelect = writable();
    let metadataSelect1 = writable();
    let metadataSelect2 = writable();
    let showLoading = writable(true);

    onMount(() => { setTimeout(() => showLoading.set(false), 1) });
    
    const plotTypeOpts = new Map([['', ["Violin", "Box", "Bar"].filter(v => allowedPlotTypes.includes(v)).map(l => ({id: l, name: l}))]])
    let plotType = writable(plotTypeOpts.values().next().value[0]);

    let scaleSelect = writable({id: 'Log 2', name: 'Log 2'});
    const scaleOpts = new Map([['', ['Linear', 'Log e', 'Log 2', 'Log 10'].map(l => ({id: l, name: l}))]])

    let expressionLinearThreshold = writable(0);

    let customSelect = writable()
    let customSelectName = 'Filter'

    function setExpressionVal(e) {
        let newVal = parseInt(e.target.value);
        if (isNaN(newVal)) newVal = 0;
        expressionLinearThreshold.set(newVal);
    }
    
    const datasetOptsObj = derived([metadataStore, filteredStore, showLoading], ([$metadataStore, $filteredStore, $showLoading], set) => {
        if($showLoading || !$metadataStore || !$filteredStore) return;
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

        // Attempt to keep selected metadata (e.g. age interval) if there is an equivalent
        let equivalentColumnIndex = metadataOptVals1.findIndex(v => v.name === get(metadataSelect1)?.name);
        let defaultColumnIndex = reader.customDefaultColumn ? metadataOptVals1.findIndex(v => v.name == reader.customDefaultColumn) : -1;
        metadataSelect1.set(metadataOptVals1[equivalentColumnIndex !== -1 ? equivalentColumnIndex : Math.max(0, defaultColumnIndex)]);
        
        // Attempt to keep filter (e.g. brain region) if there is an equivalent
        let equivalentCustomIndex = customOptVals.findIndex(v => v.name === get(customSelect)?.name);
        customSelect.set(equivalentCustomIndex !== -1 ? customOptVals[equivalentCustomIndex] : undefined);
        
        metadataSelect2.set(undefined);
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
        const pvaluesStore = reader.getMatrixStore['/metadata/' +  $datasetsSelect.id + '/matrices/' + $matrixSelect.id + "_pvalues"];
        if (pvaluesStore !== undefined) { // N.B. Custom datasets do not have computed pvalues
            const expressionSub = pvaluesStore.current.subscribe(pvalues => {
                if(pvalues) set({...$matrixOptsObj, pvalues: pvalues, $matrixSelect});
            })
            return () => expressionSub();
        } else {
            set({...$matrixOptsObj, pvalues: {data: undefined}, $matrixSelect});
        }
    })

    const plotlyArgs = derived([expressionDataObj, pvalueDataObj, metadataSelect1, metadataSelect2, plotType, expressionLinearThreshold, scaleSelect, customSelect, colorWay, groupColorWay, colorPrimary, alwaysApplyColorWay], ([$expressionDataObj, $pvalueDataObj, $metadataSelect1, $metadataSelect2, $plotType, $expressionLinearThreshold, $scaleSelect, $customSelect, $colorWay, $groupColorWay, $colorPrimary, $alwaysApplyColorWay], set) => {
        if (!$expressionDataObj || !pvalueDataObj || !$metadataSelect1 || !$expressionDataObj.expression.data) {
            set(getPlotEmpty((!$expressionDataObj || $expressionDataObj.expression.loading || $pvalueDataObj.pvalues.loading) ? 'Loading...' : 'Not in dataset'))
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

            const isCategorical = (typeof x[0]) == 'string' || x[0] instanceof String

            const csColumn = cs ? withoutNulls(reader.getColumn(reader.customFilterColumn).values) : undefined;
            
            const orderX = reader.getColumn(ms1).attrs.order
            const orderZ = ms2 && reader.getColumn(ms2).attrs.order
            
            const groupSizesX = reader.getColumn(ms1).attrs.groupSizes
            const groupLabelsX = reader.getColumn(ms1).attrs.groupLabels

            const pValIdx = reader.order.indexOf(ms1);
            let headingX = "";
            if (ms2 || $pvalueDataObj.pvalues.data === undefined) {
                headingX = ms1;
            } else {
                let statistic = $pvalueDataObj.pvalues.data.values[2 * pValIdx].toPrecision(2);
                let pval = $pvalueDataObj.pvalues.data.values[2 * pValIdx + 1];
                let pvalDisplay = pval < 10e-12 ? 'p<10e-12' : `p=${pval.toPrecision(2)}` // Minimum pvalue 10e-12
                let statisticName = isCategorical ? 'f' : 'r';
                let testName = isCategorical ? 'ANOVA' : 'Pearson cor';
                if (!isNaN(pval)) headingX = `${ms1} (${pvalDisplay}, ${statisticName}=${statistic}, ${testName})`;
            }

            let headingY = $expressionDataObj.$matrixSelect.name;
            const headingZ = ms2;

            // Only apply this input field when it is actually visible
            const threshold = $plotType.id == "Bar" ? $expressionLinearThreshold : 0;
            
            // Calculate % expressing/nonzero and add to x labels if required
            let zeroXCounts = {}
            if (isCategorical) {
                x.forEach((v, i) => {
                    let curr = zeroXCounts[v];
                    if (curr === undefined) curr = zeroXCounts[v] = [0, 0, 0];
                    if (!cs || csColumn[i] == cs) {
                        curr[0]++; // Track total count for each category
                        if (y[i] > threshold) curr[1]++; // Track greater than threshold for each category
                        if (y[i] >= 1) curr[2]++; // Track greater than 1 for each category
                    }
                });
            }

            const headingMain = `${heading} - ${ds1}` + (cs ? ` (${cs})` : ``)

            if (isCategorical && $plotType.id == "Bar") {
                // For categories, x value becomes UNIQUE categories, y value becomes % expressed
                headingY = `% ${$expressionDataObj.$matrixSelect.name} above ${threshold}`;
                let zeroXCountsEntries = Object.entries(zeroXCounts);
                let x = orderX ? orderX.filter(v => v in zeroXCounts) : Object.keys(zeroXCounts);
                let y = x.map(x => { let curr = zeroXCounts[x]; return (curr[1]/curr[0]*100); });
                set(getPlotBar(headingMain, x, y, headingX, headingY, $colorPrimary[0]));
            } else {
                // Combine and apply custom filter if necessary
                let data = getZipped({x, y, z, name: names})
                if(cs) data = data.filter((d, i) => csColumn[i] == cs)

                // Apply scale
                if($scaleSelect.id != 'Linear') {
                    headingY = `${headingY} (${$scaleSelect.id})`;
                    let fn = {"Log e": Math.log, "Log 2": Math.log2, "Log 10": Math.log10}[$scaleSelect.id];
                    if (fn === undefined) throw new Error("Unsupported scale: " + $scaleSelect.id);
                    data.forEach(v => v.y = fn(v.y + LOG_OFFSET));
                }
                
                if (isCategorical) {
                    if (!["Violin", "Box"].includes($plotType.id)) throw new Error("Unsupported plot type: " + $plotType.id);

                    // For categories that have partial expression and at least one expression > 1.0, add suffix text
                    let xSuffixes = {};
                    for (const [v, curr] of Object.entries(zeroXCounts)) {
                        if (curr[1] !== curr[0] && curr[2] > 0) xSuffixes[v] = ` (${(curr[1]/curr[0]*100).toFixed(2)}% expr)`       
                    }

                    // Update plot
                    set(getPlotDistribution(headingMain, data, headingX, headingY, headingZ, orderX, orderZ, groupLabelsX, groupSizesX, xSuffixes, $colorWay, $groupColorWay, $plotType.id.toLowerCase(), $alwaysApplyColorWay))
                } else {
                    set(getPlotScatter(headingMain, data, headingX, headingY, headingZ, orderZ, {}, $colorWay));
                }
            }
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
                <Dropdown title={customSelectName} selected={customSelect} groups={$matrixOptsObj.customOpts} optional={true}/>
            {/if}
            {#if $matrixOptsObj?.matrixOpts.get('').length > 1}
                <Dropdown title='Matrix' selected={matrixSelect} groups={$matrixOptsObj.matrixOpts}/>
            {/if}
            <Dropdown title='Metadata 1' selected={metadataSelect1} groups={$matrixOptsObj.metadataOpts1}/>

            {#if allowSecondMetadataSelect}
            <Dropdown title='Metadata 2' selected={metadataSelect2} groups={$matrixOptsObj.metadataOpts2} optional={true}/>
            {/if}

            {#if allowedPlotTypes.length > 1}
            <Dropdown title='Categorical Plot Type' selected={plotType} groups={plotTypeOpts}/>
            {/if}

            {#if $plotType.id == "Bar"}
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
