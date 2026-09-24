import * as hdf5 from 'jsfive';
import * as pako from 'pako';
import * as protobuf from '../../gen/data_pb'

// Allow possible reactivity without depending on a specific framework
class DummyStore {
    value = undefined
    set(newValue) { this.value = newValue; }
    get() { return this.value; }
}

/**
 * Get HDF5 async
 * @param {string} url 
 * @returns {Object}
 */
async function getHDF5(url, onProgress = (progress)=>{}) {
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
        onProgress(Math.floor(100 * (at / length)));
    }
    return new hdf5.File(buffer.buffer, '');
}

/**
 * Create metadata object, store base url
 * @param {string} url 
 * @returns {Object}
 */
async function createMetadata(metadataURL) {
    try { return {url: metadataURL.slice(0, metadataURL.lastIndexOf('/')), value: await (await fetch(metadataURL)).json()}; }
    catch(e) { console.log(e); return {error: `Unable to load source ${metadataURL}: (${e})`}; }
}

/**
 * Create main data object, includes hdf5 and associated row-dependent remote data
 * @param {string} url 
 * @param {function} progress callback called when download progresses
 * @param {function} rowStoreClass requires a .set function, invoked by updateAllExpressionData
 * @returns {Object}
 */
async function createData(hdf5URL, onProgress = (progress)=>{}, rowStoreClass = DummyStore) {
    const rowStreams = {}
    const obj = await getHDF5(hdf5URL, onProgress);
    for(let i=0; i<obj.attrs.remote.length; i+=3) {
        rowStreams[obj.attrs.remote[i+0]] = {
            attrs: obj.get(obj.attrs.remote[i+0]).attrs, 
            indexPath: obj.attrs.remote[i+1], 
            type: obj.attrs.remote[i+2], 
            current: rowStoreClass(),
        }
    }
    return {value: obj, rowStreams: rowStreams};
}

async function updateAllExpressionData(data, metadata, row) {
    // Determine requests
    let requests = []
    for(const [rangesPath, rowStream] of Object.entries(data.rowStreams)) {
        const index = data.value.get(rowStream.indexPath).value;
        const indexedRow = index[row];
        if(indexedRow >= 0) {
            rowStream.current.set({loading: true})
            requests.push({
                rowStream,
                byteStart: data.value.get(rangesPath).value[indexedRow*2],
                byteEnd: data.value.get(rangesPath).value[indexedRow*2+1],
            })
            console.log(rangesPath, [row, indexedRow], '->', requests[requests.length-1])
        } else {
            rowStream.current.set({emtpy: true})
        }
    }
    requests.sort((a, b) => a.byteStart - b.byteStart)

    // Perform single combined request
    const controller = new AbortController();
    const response = await fetch(metadata.url + '/expression.bin', {
        signal: controller.signal,
        headers: {'Range': 'bytes=' + `${requests[0].byteStart}-${requests[requests.length-1].byteEnd-1}`},
    });

    // Attempt to stream outputs
    if(response.status !== 206) {
        controller.abort();
        for(const rowStream of Object.values(data.rowStreams)) rowStream.current.set({error: 'Invalid response, 206 expected'});
    } else {
        const responseLen = response.headers.get('content-length');
        if (responseLen != (requests[requests.length-1].byteEnd - requests[0].byteStart)) {
            for(const rowStream of Object.values(data.rowStreams)) rowStream.current.set({error: 'Unexpected response length'})
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
                    rowStream.current.set({data: unpacked, row: row});
                } catch(e) {
                    console.log(e)
                    rowStream.current.set({error: e});
                }
                ++i;
            }
        }
    }
}

/**
 * Abstracts away hdf5 so custom data can have a common interface, caches some slow retrivals
 * Not necessary when retrieving hdf5 data only, but required for ./create.js plotting
 * @param {Object} data
 * @returns {Dict}
 */
function createReaders(data) {
    const metadataColumnReaders = {};
    for(const h of data.value.get('metadata').keys) {
        // required - metadata "column" names
        // optional - type, customDefaultColumn (used by dropdown
        const attrs = data.value.get('metadata/' + h + '/samples').attrs
        metadataColumnReaders[h] = {               
            ...attrs,           
            type: attrs.type, 
            sampleNames: data.value.get('metadata/' + h + '/sample_names').value,
            matrixNames: data.value.get('metadata/' + h + '/matrices').keys.filter(m => !m.endsWith('_pvalues')),
            getMatrixStore: data.rowStreams,
            getColumn: (colHeading) => {
                const sRoot = data.value.get('metadata/' + h + '/samples/' + colHeading)
                return {values: sRoot.value, attrs: sRoot.attrs} // groupSizes, groupLabels, order (of categories), etc...
            },
        }
    }
    return metadataColumnReaders;
}

function GetGeneIds(data) {
    return data.get('data/Ensembl ID').value;
}

/**
 * Get an overview of all available nested data and associated types
 * Note some datasets have an index for looking up remote byte ranges, but consumers should just use updateAllExpressionData
 * @param {Object} data
 * @returns {string}
 */
function GetHDF5KeysJson(data) {
    return JSON.stringify(GetHDF5Keys(data));
}

function GetHDF5KeysRecursive(data) {
    if (!data.keys.length) return typeof data.value[0]
    return Object.fromEntries(data.keys.map(k => [k, GetHDF5KeysRecursive(data.get(k))]));
}

function GetHDF5Keys(data) {
    return GetHDF5KeysRecursive(data.get("/"));
}

export { createMetadata, createData, updateAllExpressionData, createReaders }