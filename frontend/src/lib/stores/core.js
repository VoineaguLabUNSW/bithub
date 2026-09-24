
import { asyncDerived, asyncReadable, writable, derived, get } from "@square/svelte-store";
import { createData, createMetadata, updateAllExpressionData, createReaders } from '../utils/readers';

/**
 * Awaitable lazy expression data store for given HDF5 url
 * @param {string} url 
 * @returns {Object}
 */
function createCore(url) {
    const progress = writable(0);
    const row = writable(undefined);

    const metadata = asyncDerived(url, createMetadata); 

    const data = asyncDerived(
        metadata,
        async ($metadata) => {
            try {             
                return await createData($metadata.url + '/out.hdf5', progress.set, writable);
            } catch (e) {
                console.log(e)
                return {error: e};
            }
        },
    );

    row.subscribe(async ($row) => {
        // NOTE: could not use asyncDerived([row, data]) since data is not json serializable
        let $data;
        let $metadata;
        if($row === undefined || !($data = get(data)) || !($metadata = get(metadata))) return
        await updateAllExpressionData($data, $metadata, $row);
    });

    const customs = writable({});

    const readers = derived([data, customs], ([$data, $customs]) => {
        const customReaders = {};
        for(let cd of Object.values($customs)) customReaders[cd.name] = cd.metadataColumnReader;
        return {...createReaders($data), ...customReaders};
    });
    
    return { data, metadata, progress, row, readers, customs}
}

export { createCore };
