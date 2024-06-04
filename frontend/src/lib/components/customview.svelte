<script>
    import { Fileupload, Label, Button, Helper, Input } from 'flowbite-svelte';
    import { getContext } from 'svelte'
    import { writable, derived } from 'svelte/store'
    import { base } from '$app/paths';
    import { asCSV } from '../stores/custom'
    import { findMatchesSorted } from "../utils/hdf5";
    import {count, mean, sd} from '../utils/math'

    export let customModal;
    
    const { row, data, customs } = getContext('core');

    const dataFiles = writable();
    const metadataFiles = writable();

    const dataContent = asCSV(dataFiles)
    const metadataContent = asCSV(metadataFiles);

    let nameInputValue;
    const placeholderName = derived(customs, $customs => `Custom Dataset ${1+Object.keys($customs).length}`)

    const dataProcessed = derived([dataContent, data], ([$dataContent, $data], set) => {
        if(!$dataContent?.result) {
            if($dataContent?.error) set($dataContent)
        } else {
            set({loading: true})
            const matrix = $dataContent.result;

            // Match rows
            const headings = $data.value.get('data').attrs.order;
            const ensemblIds = $data.value.get('data/' + headings[0]).value;
            const userEnsemblIds = matrix.slice(1).map(row => row[0]);
            const ensemblMatches = findMatchesSorted([ensemblIds], userEnsemblIds);
            if(ensemblMatches.length == 0) {
                set({error: 'No strings in the first column matched to Ensembl IDs'});
                return
            }

            const sampleNames = matrix[0].slice(1);
            const index = new Array(ensemblIds.length).fill(-1)
            ensemblMatches.forEach(m => index[m.rowIndex] = m.searchIndex)
            
            // Calculate zscores for matches, remove left column
            const logs = []
            let nanCount = 0
            for(let i=1; i<matrix.length; ++i) {
                const rowData = matrix[i].slice(1).map(v => parseFloat(v))
                nanCount += count(rowData, isNaN)
                matrix[i] = rowData
                logs.push(mean(rowData.map(v => Math.log2(Math.abs(v || 0) + 0.01))))
            }
            const logMean = mean(logs)
            const logSD = sd(logs, logMean) || 0.0000000001
            const zScores = logs.map(x => (x - logMean) / logSD)
            if(nanCount > (matrix.length * matrix[0].length / 2)) {
                set({error: 'File does not appear to be a decimal matrix (half were NaN)'})
                return                
            }

            set({result: {index, zScores, matrix, sampleNames}})
        }
    })

    let metadataProcessed = derived([dataProcessed, metadataContent], ([$dataProcessed, $metadataContent], set) => {
        if($metadataContent?.error) set($metadataContent)
        else if($dataProcessed?.result) {
            let expressionGetter = undefined;
            let columnGetter = undefined;
            let metadataNames = undefined;
            let commonSamples = undefined;

            if($metadataContent?.result) {
                const matrix = $metadataContent.result;
                metadataNames = matrix[0].splice(1)
                const sampleNames = matrix.slice(1).map(row => row[0]);
                const sampleMatches = findMatchesSorted([sampleNames.map(s => s.toUpperCase())], $dataProcessed.result.sampleNames);
                commonSamples = sampleMatches.map(m => sampleNames[m.rowIndex])
                if(commonSamples.length == 0) {
                    set({error: 'Sample column in metadata must match first row of expression matrix'})
                    return
                }

                // Create columns
                const columns = {}
                const NA_VAL = 'NA';
                for(let i=0; i<metadataNames.length; ++i) {
                    let column = sampleNames.map((_, j) => matrix[j+1][i+1]);

                    // Convert to numeric if possible
                    if(count(column.filter(v => v != NA_VAL), isNaN) == 0) {
                        column = column.map(v => parseFloat(v) || 0)
                    }
                    columns[metadataNames[i]] = column
                }

                // Get expression/columns WITHOUT unmatched samples
                expressionGetter = derived(row, ($row, set) => {
                    if($row === undefined) return;
                    const rowIndex = $dataProcessed.result.index[$row]
                    if(rowIndex == -1) return;
                    const rowData = $dataProcessed.result.matrix[rowIndex+1]
                    let ret = {data: {values: sampleMatches.map(m => rowData[m.searchIndex])}}
                    set(ret)
                })
                columnGetter = (colHeading) => {
                    const columnData = columns[colHeading];
                    return {attrs: {}, values: sampleMatches.map(m => columnData[m.searchIndex])}
                }
            }
            set({result: {order: metadataNames, sampleNames: commonSamples, $dataProcessed, expressionGetter, columnGetter}})
        }
    });

    function finaliseDataset($metadataProcessed, name) {
        const matrixName = 'Custom'
        const {order, sampleNames, expressionGetter, columnGetter} = $metadataProcessed.result
        const {index, zScores } = $metadataProcessed.result.$dataProcessed.result
        return ({
            [name]: {
                name,
                index,
                zScores,
                metadataColumnReader: order && ({
                    order,
                    sampleNames,
                    matrixNames: [matrixName],
                    getMatrixStore: {[`/metadata/${name}/matrices/${matrixName}`]: {current: expressionGetter}},
                    getColumn: columnGetter
                })
            }
        });
    }


</script>

<div>
    <div class='mb-4'>
        <p>Adds columns and charts for local comparison - no data is shared with BITHub.</p>
        <p>Contact Voineagu Lab for permanent additions.</p>
    </div>

    <form>
        <Label class="space-y-2 mb-4">
            <span>Dataset Name</span>
            <Input bind:value={nameInputValue} type="text"  placeholder={$placeholderName} required />
        </Label>

        <Label class="space-y-2 mb-4">
            <span>Load Expression Matrix</span>
            <a class='underline' href='{base}/BrainSeq-exp-example.csv'>(e.g. BrainSeq-exp-example.csv)</a>
            <Fileupload bind:files={$dataFiles}/>
            <Helper color={$dataProcessed?.error ? 'red' : undefined}>Ensembl gene IDs (first column) x sample names (first row){$dataProcessed?.error ? ` - Error: ${$dataProcessed.error }` : ''}.</Helper>
        </Label>

        <Label class="space-y-2 mb-4">
            <span>Load Metadata</span>
            <a class='underline' href='{base}/BrainSeq-metadata-example.csv'>(e.g. BrainSeq-metadata-example.csv)</a>
            <Fileupload bind:files={$metadataFiles}/>
            <Helper color={$metadataProcessed?.error ? 'red' : undefined}>Sample names (first column) x metadata variables (first row){$metadataProcessed?.error ? ` - Error: ${$metadataProcessed.error }` : ''}.</Helper>
        </Label>

        <div class='flex flex-col items-center'>
            <Button type='submit' disabled={!$metadataProcessed?.result} on:click={() => {customs.set({...$customs, ...finaliseDataset($metadataProcessed, nameInputValue || $placeholderName)}); customModal.set('')}} color='light'>Add<i class='mx-2 fas fa-plus'/></Button>
        </div>
    </form>
</div>