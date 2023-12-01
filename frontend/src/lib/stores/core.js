import * as hdf5 from 'jsfive';
import * as fflate from 'fflate';
import { asyncDerived, asyncReadable, writable, derived, get } from "@square/svelte-store";

/**
 * Get HDF5 async
 * @param {string} url 
 * @returns {Object}
 */
async function getHDF5(url, setProgress) {
    const response = await fetch(url);
    const length = response.headers.get('Content-Length');
    const buffer = new Uint8Array(length);
    let at = 0;
    const reader = response.body.getReader();
    for (; ;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer.set(value, at);
        at += value.length;
        setProgress(Math.floor(100 * (at / length)));
    }
    return new hdf5.File(buffer.buffer, '');
}

function bufferToRow(buffer, knownLen) {
    const inflated = fflate.unzlibSync(buffer);
    const dataView = new DataView(inflated.buffer);
    const is_sparse = dataView.getUint8(0, true)
    const array = []
    if(is_sparse) {
        for(let i=1; i<inflated.byteLength; i+=(4 + 4)) {
            let index = dataView.getInt32(i, true)
            array[index] = dataView.getFloat32(i+4, true);
        }
    } else {
        for(let i=0; i<knownLen; ++i) {
            array[i] = dataView.getFloat32(1 + i*4, true);
        }
    }
    return array
}

async function getJSON(url) {
    const req = await fetch(url);
    return await req.json();
}

/**
 * Awaitable lazy expression data store for given HDF5 url
 * @param {string} url 
 * @returns {Object}
 */
function createCore(url) {
    const progress = writable(0);
    const row = writable(undefined);

    const metadata = asyncReadable(
        undefined, 
        async () => {
            try { return {value: await getJSON(url)}; } 
            catch(e) { console.log(e); return {error: e}; }
        }
    );

    const data = asyncDerived(
        metadata,
        async ($metadata) => {
            try {
                const rowStreams = {}
                const obj = await getHDF5(/*$metadata.value.data_url*/'https://d33ldq8s2ek4w8.cloudfront.net/bithub/out.hdf5', progress.set);
                const md = obj.get('metadata')
                for(let d of md.keys.filter(d => md.get(d).keys.includes('matrices'))) {
                    for(let m of md.get(d + '/matrices').keys) {
                        const id = d + ':' + m;
                        const length = obj.get(`metadata/${d}/matrices/${m}`).attrs.shape[1]
                        rowStreams[id] = {length, current: writable(undefined)}
                    }
                }
                return {value: obj, rowStreams: rowStreams};
            } catch (e) {
                return {error: e};
            }
        },
    );

    row.subscribe(async ($row) => {
        // NOTE: could not use asyncDerived([row, data]) since data is not json serializable
        let $data;
        if($row === undefined || !($data = get(data))) return

        // Determine requests
        const requests = []
        for(const [id, rowStream] of Object.entries($data.rowStreams)) {
            
            const [d, m] = id.split(':');
            const index = $data.value.get(`data/${d}`).value;
            const indexedRow = index[$row];
            if(indexedRow >= 0) {
                rowStream.current.set({loading: true})
                requests.push({
                    id,
                    length: rowStream.length,
                    byteStart: $data.value.get(`metadata/${d}/matrices/${m}/start`).value[indexedRow],
                    byteEnd: $data.value.get(`metadata/${d}/matrices/${m}/end`).value[indexedRow]
                })
            } else {
                rowStream.current.set({emtpy: true})
            }
        }
        requests.sort((a, b) => a.byteStart - b.byteStart)

        // Perform single combined request
        const controller = new AbortController();
        const response = await fetch('https://d33ldq8s2ek4w8.cloudfront.net/bithub/expression.bin', {
            signal: controller.signal,
            headers: {'Range': 'bytes=' + `${requests[0].byteStart}-${requests[requests.length-1].byteEnd-1}`},
        });

        // Attempt to stream outputs
        if(response.status !== 206) {
            controller.abort();
            for(const rowStream of Object.values($data.rowStreams)) rowStream.current.set({error: 'Invalid response, 206 expected'});
        } else {
            const responseLen = response.headers.get('content-length');
            if (responseLen != (requests[requests.length-1].byteEnd - requests[0].byteStart)) {
                for(const rowStream of Object.values($data.rowStreams)) rowStream.current.set({error: 'Unexpected response length'})
            }
            let i=0;
            let o = requests[0].byteStart
            let receivedBytes=0;
            let chunksAll = new Uint8Array(responseLen);
            const reader = response.body.getReader();
            for (; ;) {
                const { done, value } = await reader.read();
                if (done) break;
                chunksAll.set(value, receivedBytes)
                receivedBytes += value.length
                while(i<requests.length && ((requests[i].byteEnd-o) <= receivedBytes)) {
                    const part = chunksAll.subarray(requests[i].byteStart-o, requests[i].byteEnd-o)
                    const rowStream = $data.rowStreams[requests[i].id];
                    try {
                        const unpacked = bufferToRow(part, requests[i].length);
                        rowStream.current.set({data: unpacked, row: $row});
                    } catch(e) {
                        console.log(e)
                        rowStream.current.set({error: e});
                    }
                    ++i;
                }
            }
        }
    });
    return { data, metadata, progress, row}
}

export { createCore };