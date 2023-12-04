import { derived, writable } from 'svelte/store'
import Papa from 'papaparse';

function asCSV(fileStore) {
    return derived(fileStore, ($fileStore, set) => {
        if(!$fileStore) return
        set({loading: true})
        Papa.parse($fileStore[0], {
            dynamicTyping: false,
            error: (e) => set({error: `Could not parse file: ${e.type}`}),
            complete: (e) => {
                if(!e.truncated && !e.aborted) {

                    // Guarantees/fixes square matrix
                    let matrix = e.data;

                    if(matrix.length < 2) {
                        set({error: 'At least two rows (including header) required'})
                        return
                    }

                    // Attempt to detect and remove null corner
                    const numCols = matrix[1].length
                    if(matrix[0].length == numCols - 1) {
                        matrix[0].unshift('')
                    } else if(matrix[0].length != numCols) {
                        set({error: 'Each column must have a heading'})
                        return
                    }

                    matrix = matrix.filter(row => row.length == numCols)

                    set({result: matrix})
                }
            }
        });
    });
}

export { asCSV }