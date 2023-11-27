import { derived } from "@square/svelte-store";

function findMatchesSorted(arrays, searches) {
    searches.sort();
    arrays.forEach(a => a.sort());
    let indices = new Array(arrays.length).fill(0)
    let ret = []
    for(const term of searches) {
        for(const [i, arr] of arrays.entries()) {
            let cmp = -1;
            while(indices[i]<arr.length && cmp < 0) {
                cmp = arr[indices[i]].localeCompare(term, undefined, { sensitivity: 'accent' })
                if(cmp < 0) indices[i]++;
            }
            if (cmp === 0) {
                ret.push(indices[i]);
                break;
            }
        }
    }
    return ret;
}

function createCombinedStore(data, customDatasets) {
    return derived([data, customDatasets], ([$data, $customDatasets], set) => {
        if($data?.value) {
            const headings = $data.value.get('data').attrs.order;
            const original = headings.map(k => $data.value.get('data/' + k).value);
            const [isDs, isDb] = [$data.value.get('data').attrs.isDataset, $data.value.get('data').attrs.isDatabase]
            const indices = headings.map((h, i) => (isDs[i] || isDb[i]) ? $data.value.get('metadata/' + h + '/scaled').value : undefined)
            const columnStringSizes = headings.map(k => $data.value.get('data/' + k).dtype).map(dt => dt.startsWith('S') ? parseInt(dt.slice(1)) : undefined);
            const headingsDefaultVisible = $data.value.get('data').attrs.defaultVisible.map(i => headings[i])

            for(let h of $customDatasets) {
                const insertPoint = isDs.indexOf(1)
                headings.splice(insertPoint, 0, h)
                original.splice(insertPoint, 0, new Array(original[0].length).fill(0))
                isDs.splice(insertPoint, 0, 1)
                indices.splice(insertPoint, 0, [3.8])
                columnStringSizes.splice(insertPoint, 0, undefined)
            }

            const boolToIndices = (array) => array.map((v, i) => v ? i : undefined).filter(x => x !== undefined);
            const datasetIndices = boolToIndices(isDs)
            const databaseIndices = boolToIndices(isDb)
            const generalIndices = boolToIndices(headings.map((_, i) => !isDs[i] && !isDb[i]))
            
            const columns = [...generalIndices.map(i => original[i]), ...datasetIndices.concat(databaseIndices).map(col_i => original[col_i].map(v => v === -1 ? Number.NEGATIVE_INFINITY : indices[col_i][v]))]
            const headingGroups = new Map([['', generalIndices.map(i => headings[i])], ['Datasets', datasetIndices.map(i => headings[i])], ['Databases', databaseIndices.map(i => headings[i])]])
            set({headings, headingsDefaultVisible, original, columns, generalIndices, datasetIndices, databaseIndices, columnStringSizes, headingGroups})
        }
    });
}

function createFilteredStore(columnStore, currentSearch, currentVisibleCombined) {
    return derived([columnStore, currentSearch, currentVisibleCombined], ([$columnStore, $currentSearch, $currentVisibleCombined], set) => {
        if ($columnStore) {
            const columns = $columnStore.columns;
            let filtered = Array.from(Array(columns[0].length).keys());

            if($currentSearch) {
                const searchTerms = $currentSearch.split(',').map(st => st.trim().toLowerCase())
                searchTerms.sort()

                if(searchTerms.length == 1) {
                    const searchable = $columnStore.columns.map((_, col_i) => col_i).filter(col_i => $columnStore.columnStringSizes[col_i]).filter(col_i => $currentVisibleCombined.includes($columnStore.headings[col_i]))
                    filtered = filtered.filter(row_i => searchable.some(col_i => $columnStore.columns[col_i][row_i].toLowerCase().includes(searchTerms[0])))
                } else {
                    const exactSearchable = [0, 1].filter(col_i => $currentVisibleCombined.includes($columnStore.headings[col_i])).map(col_i => columns[col_i])
                    filtered = findMatchesSorted(exactSearchable, searchTerms);
                }
            }
            set({...$columnStore, results: filtered})
        }
    })
}

export { createCombinedStore, createFilteredStore }