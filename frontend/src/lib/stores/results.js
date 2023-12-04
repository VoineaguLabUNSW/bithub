import { withoutNulls } from "$lib/utils/hdf5";
import { derived } from "svelte/store";

function findMatchesSorted(arrays, searches) {
    searches.sort();
    arrays = arrays.map(a => [...withoutNulls(a).entries()])
    arrays.forEach(a => a.sort((a, b) => a[1].localeCompare(b[1])));
    
    let indices = new Array(arrays.length).fill(0)
    let ret = []
    for(const term of searches) {
        for(const [i, arr] of arrays.entries()) {
            let cmp = -1;
            while(indices[i]<arr.length && cmp < 0) {
                cmp = arr[indices[i]][1].localeCompare(term, undefined, { sensitivity: 'accent' })
                if(cmp <= 0) indices[i]++;
            }
            if (cmp === 0) {
                ret.push(arr[indices[i]-1][0]);
                break;
            }
        }
    }
    return ret;
}

function createCombinedResultsStore(data, customDatasets) {
    return derived([data, customDatasets], ([$data, $customDatasets], set) => {
        if($data?.value) {
            const headings = $data.value.get('data').attrs.order;
            const original = headings.map(k => $data.value.get('data/' + k).value);
            const [isDs, isDb] = [$data.value.get('data').attrs.isDataset, $data.value.get('data').attrs.isDatabase]
            const indices = headings.map((h, i) => (isDs[i] || isDb[i]) ? $data.value.get('metadata/' + h + '/scaled').value : undefined)
            const columnStringSizes = headings.map(k => $data.value.get('data/' + k).dtype).map(dt => dt.startsWith('S') ? parseInt(dt.slice(1)) : undefined);
            const headingsDefaultVisible = $data.value.get('data').attrs.defaultVisible.map(i => headings[i])

            for(let cd of $customDatasets) {
                const insertPoint = isDs.indexOf(1)
                headings.splice(insertPoint, 0, cd.name)
                original.splice(insertPoint, 0, cd.mapping)
                isDs.splice(insertPoint, 0, 1)
                indices.splice(insertPoint, 0, cd.zscores)
                columnStringSizes.splice(insertPoint, 0, undefined)
            }

            const boolToIndices = (array) => array.map((v, i) => v ? i : undefined).filter(x => x !== undefined);
            const datasetIndices = boolToIndices(isDs)
            const databaseIndices = boolToIndices(isDb)
            const generalIndices = boolToIndices(headings.map((_, i) => !isDs[i] && !isDb[i]))
            
            const columns = [...generalIndices.map(i => original[i]), ...datasetIndices.concat(databaseIndices).map(col_i => original[col_i].map(v => v === -1 ? Number.NEGATIVE_INFINITY : indices[col_i][v]))]
            const headingGroups = new Map([['', generalIndices.map(i => headings[i])], ['Datasets', datasetIndices.map(i => headings[i])], ['Databases', databaseIndices.map(i => headings[i])]])
            
            const groupIndices = {}
            for(const group of $data.value.get('panels').keys) {
                groupIndices[group] = datasetIndices.filter(col_i => $data.value.get('panels/' + group).keys.includes(headings[col_i]))
            }
            groupIndices['_varpart'] = datasetIndices.filter(col_i => $data.value.get('metadata/' + headings[col_i]).keys.includes('variance_partition'))
            groupIndices['_transcripts'] = datasetIndices.filter(col_i => $data.value.get('metadata/' + headings[col_i]).keys.includes('transcripts'))
            set({headings, headingsDefaultVisible, original, columns, generalIndices, datasetIndices, databaseIndices, groupIndices, columnStringSizes, headingGroups})
        }
    });
}

function createFilteredResultsStore(columnStore, currentSearch, currentVisibleCombined) {
    return derived([columnStore, currentSearch, currentVisibleCombined], ([$columnStore, $currentSearch, $currentVisibleCombined], set) => {
        if ($columnStore) {
            const columns = $columnStore.columns;
            let results = Array.from(Array(columns[0].length).keys());

            let datasetIndicesResults = $columnStore.datasetIndices
            if($currentSearch) {
                const searchTerms = $currentSearch.split(',').map(st => st.trim().toLowerCase())
                searchTerms.sort()

                if(searchTerms.length == 1) {
                    const searchable = columns.map((_, col_i) => col_i).filter(col_i => $columnStore.columnStringSizes[col_i]).filter(col_i => $currentVisibleCombined.includes($columnStore.headings[col_i]))
                    results = results.filter(row_i => searchable.some(col_i => $columnStore.columns[col_i][row_i].toLowerCase().includes(searchTerms[0])))
                } else {
                    const exactSearchable = [0, 1].filter(col_i => $currentVisibleCombined.includes($columnStore.headings[col_i])).map(col_i => columns[col_i])
                    results = findMatchesSorted(exactSearchable, searchTerms);
                }
                datasetIndicesResults = datasetIndicesResults.filter(col_i => results.some(row_i => $columnStore.original[col_i][row_i] >= 0))
            }
            set({...$columnStore, results, datasetIndicesResults})
        }
    })
}

function createSelectedResultsStore(columnStore, row) {
    return derived([columnStore, row], ([$columnStore, $row], set) => {
        if($columnStore && $row !== undefined) {
            const results = $row !== undefined ? [$row] : [];
            const datasetIndicesResults = $columnStore.datasetIndices.filter(col_i => $columnStore.original[col_i][$row] >= 0)
            set({...$columnStore, results, datasetIndicesResults})
        }
    })
}

function getFilteredStoreGroup(filteredStore, group) {
    return derived(filteredStore, ($filteredStore, set) => {
        const groupIndices = $filteredStore.groupIndices[group]
        const datasetIndicesResults = $filteredStore.datasetIndicesResults.filter(col_i => groupIndices.includes(col_i))
        if($filteredStore) set({...$filteredStore, datasetIndicesResults})
    })
}

export { createCombinedResultsStore, createFilteredResultsStore, createSelectedResultsStore, getFilteredStoreGroup};