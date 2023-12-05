import { derived, writable } from 'svelte/store'
import Papa from 'papaparse';

function asCSV(fileStore, forceRectangle=true, minCols=2, minRows=2) {
    return derived(fileStore, ($fileStore, set) => {
        if(!$fileStore) return
        set({loading: true})
        Papa.parse($fileStore[0], {
            dynamicTyping: false,
            error: (e) => set({error: `Could not parse file: ${e.type}`}),
            complete: (e) => {
                if(!e.truncated && !e.aborted) {
                    try {
                        // Guarantees/fixes square matrix
                        let matrix = e.data;

                        if(matrix.length < minRows) throw Error(`At least ${minRows} rows (including headers) required`);

                        // Attempt to detect and remove null corner
                        const numCols = matrix[1].length
                        if(matrix[0].length == numCols - 1) {
                            matrix[0].unshift('')
                        } else if(matrix[0].length != numCols) {
                            throw Error('Each column must have a heading')
                        }
                        
                        if(matrix[0].length < minCols) throw Error(`At least ${minCols} columns (including headers) required`);

                        if(forceRectangle) matrix = matrix.filter(row => row.length == numCols)

                        set({result: matrix})
                    } catch(e) {
                        set({error: e})
                    }
                }
            }
        });
    });
}

export { asCSV }