import { findMatchesSorted } from "../utils/hdf5";
import { derived } from "svelte/store";

function createCombinedResultsStore(data, customDatasets) {
    return derived([data, customDatasets], ([$data, $customDatasets], set) => {
        if($data?.value) {
            const headings = $data.value.get('data').attrs.order;
            const original = headings.map(k => $data.value.get('data/' + k).value);
            const [isDs, isDb] = [$data.value.get('data').attrs.isDataset, $data.value.get('data').attrs.isDatabase]
            const indices = headings.map((h, i) => (isDs[i] || isDb[i]) ? $data.value.get('metadata/' + h + '/scaled').value : undefined)
            const columnStringSizes = headings.map(k => $data.value.get('data/' + k).dtype).map(dt => dt.startsWith('S') ? parseInt(dt.slice(1)) : undefined);
            const headingsDefaultVisible = $data.value.get('data').attrs.defaultVisible.map(i => headings[i])
            

            const boolToIndices = (array) => array.map((v, i) => v ? i : undefined).filter(x => x !== undefined);
            let datasetIndices = boolToIndices(isDs);

            const customDatasetVals = Object.values($customDatasets)
            const groupIndices = {}
            groupIndices['_custom'] = customDatasetVals.map((_, i) => i + isDs.indexOf(1))
            for(let cd of customDatasetVals) {
                const insertPoint = isDs.indexOf(1)
                headings.splice(insertPoint, 0, cd.name)
                original.splice(insertPoint, 0, cd.index)
                isDs.splice(insertPoint, 0, 1)
                indices.splice(insertPoint, 0, cd.zScores)
                columnStringSizes.splice(insertPoint, 0, undefined)
                headingsDefaultVisible.push(cd.name)
            }

            datasetIndices = boolToIndices(isDs)
            const databaseIndices = boolToIndices(isDb)
            const generalIndices = boolToIndices(headings.map((_, i) => !isDs[i] && !isDb[i]))
            
            const columns = [...generalIndices.map(i => original[i]), ...datasetIndices.concat(databaseIndices).map(col_i => original[col_i].map(v => v === -1 ? Number.NEGATIVE_INFINITY : indices[col_i][v]))]
            const headingGroups = new Map([['', generalIndices.map(i => headings[i])], ['Datasets', datasetIndices.map(i => headings[i])], ['Databases', databaseIndices.map(i => headings[i])]])
            
            const dsKeys = $data.value.get('metadata').keys
            for(const group of $data.value.get('panels').keys) {
                groupIndices[group] = dsKeys.filter(h => $data.value.get('panels/' + group).keys.includes(h)).map(h => headings.indexOf(h))
            }
            groupIndices['_varpart'] = dsKeys.filter(h => $data.value.get('metadata/' + h).keys.includes('variance_partition')).map(h => headings.indexOf(h))
            groupIndices['_transcripts'] = dsKeys.filter(h => $data.value.get('metadata/' + h).keys.includes('transcripts')).map(h => headings.indexOf(h))
            
            set({headings, headingsDefaultVisible, original, columns, generalIndices, datasetIndices, databaseIndices, groupIndices, columnStringSizes, headingGroups})
        }
    });
}

function createFilteredResultsStore(columnStore, currentSearch, currentVisibleCombined, currentIndexSubset) {
    return derived([columnStore, currentSearch, currentVisibleCombined, currentIndexSubset], ([$columnStore, $currentSearch, $currentVisibleCombined, $currentIndexSubset], set) => {
        if ($columnStore) {
            const columns = $columnStore.columns;
            let results = $currentIndexSubset || Array.from(Array(columns[0].length).keys());
            let datasetIndicesResults = $columnStore.datasetIndices
            if($currentSearch) {
                const searchTerms = $currentSearch.split(',').map(st => st.trim().toLowerCase())
                searchTerms.sort()

                if(searchTerms.length == 1) {
                    const searchable = columns.map((_, col_i) => col_i).filter(col_i => $columnStore.columnStringSizes[col_i]).filter(col_i => $currentVisibleCombined.includes($columnStore.headings[col_i]))
                    results = results.filter(row_i => searchable.some(col_i => $columnStore.columns[col_i][row_i].toLowerCase().includes(searchTerms[0])))
                } else {
                    const exactSearchable = [0, 1].filter(col_i => $currentVisibleCombined.includes($columnStore.headings[col_i])).map(col_i => results.map(row_i => columns[col_i][row_i]))
                    results = findMatchesSorted(exactSearchable, searchTerms).map(obj => obj.rowIndex);
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

function getFilteredStoreGroup(filteredStore, groups) {
    return derived(filteredStore, ($filteredStore, set) => {
        const groupIndices = groups.map(group => $filteredStore.groupIndices[group]).flat()
        const datasetIndicesResults = $filteredStore.datasetIndicesResults.filter(col_i => groupIndices.includes(col_i))
        if($filteredStore) set({...$filteredStore, datasetIndicesResults})
    })
}

function getFilteredStoreAll(filteredStore) {
    return derived(filteredStore, ($filteredStore, set) => {
        if($filteredStore) set({...$filteredStore, datasetIndicesResults: $filteredStore.datasetIndices})
    });
}

export { createCombinedResultsStore, createFilteredResultsStore, createSelectedResultsStore, getFilteredStoreGroup, getFilteredStoreAll};