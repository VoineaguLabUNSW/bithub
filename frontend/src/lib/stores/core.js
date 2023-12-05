import * as hdf5 from 'jsfive';
import * as pako from 'pako';
import { asyncDerived, asyncReadable, writable, derived, get } from "@square/svelte-store";
import * as protobuf from '../../gen/data_pb'

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
                const obj = await getHDF5($metadata.value.data_url/*'http://localhost:5501/out.hdf5'*/, progress.set);
                for(let i=0; i<obj.attrs.remote.length; i+=3) {
                    rowStreams[obj.attrs.remote[i+0]] = {
                        attrs: obj.get(obj.attrs.remote[i+0]).attrs, 
                        indexPath: obj.attrs.remote[i+1], 
                        type: obj.attrs.remote[i+2], 
                        current: writable(undefined)
                    }
                }                
                return {value: obj, rowStreams: rowStreams};
            } catch (e) {
                console.log(e)
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
        for(const [rangesPath, rowStream] of Object.entries($data.rowStreams)) {
            const index = $data.value.get(rowStream.indexPath).value;
            const indexedRow = index[$row];
            if(indexedRow >= 0) {
                rowStream.current.set({loading: true})
                requests.push({
                    rowStream,
                    byteStart: $data.value.get(rangesPath).value[indexedRow*2],
                    byteEnd: $data.value.get(rangesPath).value[indexedRow*2+1],
                })
            } else {
                rowStream.current.set({emtpy: true})
            }
        }
        requests.sort((a, b) => a.byteStart - b.byteStart)

        // Perform single combined request
        const controller = new AbortController();
        const response = await fetch('https://d33ldq8s2ek4w8.cloudfront.net/bithub3/expression.bin'/*'http://localhost:5501/expression.bin'*/, {
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
                    const rowStream = requests[i].rowStream
                    try {
                        let unpacked = protobuf[rowStream.type].fromBinary(pako.inflate(part))
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
    
    return { data, metadata, progress, row, customs: writable({})}
}

export { createCore };