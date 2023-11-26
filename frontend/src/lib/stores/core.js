import { meros } from 'meros/browser';
import * as hdf5 from 'jsfive';
import * as fflate from 'fflate';
import { asyncDerived, asyncReadable, writable } from "@square/svelte-store";

/**
 * Custom store to expose internal subscription events
 * @param {string} id 
 * @param {*} onSubscriberCountChange 
 * @returns {Object}
 */
function createTransparentStore(id, onSubscriberCountChange) {
    const subscribers = new Set()
    const helper = (subscribeMutator) => {
        const prevSize = subscribers.size;
        subscribeMutator();
        onSubscriberCountChange(id, prevSize, subscribers.size);
    }

    const subscribe = (cb) => {
        helper(() => subscribers.add(cb));
        return (cb) => helper(() => subscribers.delete(cb))
    }
    return {
        id,
        subscribe,
        set: (data) => subscribers.forEach(s => s(data)),
        subscriberCount: () => subscribers.size
    }
}

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

const timeout = (ms) => {
    return new Promise((resolve) => setTimeout(resolve, ms));
};

async function getJSON(url) {
    const req = await fetch(url)
    await timeout(2000);
    return await req.json();
}

/**
 * Awaitable lazy expression data store for given HDF5 url
 * @param {string} url 
 * @returns {Object}
 */
function createCore(url) {
    const matrixLoaders = {}
    let _data = undefined;
    let _row = undefined;

    const progress = writable(0);
    const row = writable(0);

    const metadata = asyncReadable (
        undefined, 
        async () => {
            try {
                return {value: await getJSON(url)}
            } catch(e) {
                return {error: e}
            }
        }
    );

    const data = asyncDerived (
        (metadata),
        async ($metadata) => {
            try {
                const obj = await getHDF5($metadata.value.data_url, progress.set)
                const updateLazy = async (id, prev, curr) => (!prev && curr) && await update(_row, obj, [id]);
                const md = obj.get('metadata')
                for(let d of md.keys.filter(d => md.get(d).keys.includes('matrices'))) {
                    for(let m of md.get(d + '/matrices').keys) {
                        const id = d + ':' + m
                        matrixLoaders[id] = createTransparentStore(id, updateLazy)
                    }
                }
                _data = obj
                return {value: obj}
            } catch (e) {
                return {error: e}
            }
        },
    );

    async function update(latest_row, latest_data, ids) {
        if(latest_data === undefined || latest_row === undefined) return

        const requests = []
        for(let id of ids) {
            matrixLoaders[id].set({loading: true});

            // Create inclusive byte requests
            const [d, m] = id.split(':')
            const index = latest_data.get(`metadata/${d}/matrices/${m}/index`).value
            requests.push({
                id,
                length: latest_data.get(`metadata/${d}/matrices/${m}`).attrs.shape[1],
                byteStart: index[latest_row],
                byteEnd: index[latest_row+1]-1
            })
        }
        requests.sort((a, b) => a.byteStart - b.byteStart)

        const controller = new AbortController();
        const response = await fetch('https://bithub-data.netlify.app/Velmeshev_CPM.matrix', {
            signal: controller.signal,
            headers: {'Range': 'bytes=' + requests.map(r => `${r.byteStart}-${r.byteEnd}`).join(',')}
        });
        if(response.status !== 206) {
            controller.abort();
            for(let id of ids) {
                matrixLoaders[id].set({error: Error('Invalid response, 206 expected')})
            }
        } else {
            // Stream range results reactively
            let i=0
            const enc = new TextEncoder();
            let parts = ids.length > 1 ? await meros(response) : [response]
            
            for await (const part of parts) {
                const r = requests[i++];
                try{
                    let array = undefined
                    let content_header, valid;
                    if(content_header = part.headers.get('content-length')) {
                        valid = (content_header == (r.byteEnd - r.byteStart + 1))
                    } else if(content_header = part.headers.get('content-range')) {
                        valid = content_header.startsWith(`bytes ${r.byteStart}-${r.byteEnd}/`)
                    }
                    if (!valid) throw Error('Unexpected range')

                    try {
                        const inflated = fflate.unzlibSync(enc.encode(part.body).buffer);
                        const dataView = new DataView(inflated.buffer);
                        const is_sparse = dataView.getUint8(0, true)
                        array = new Array(r.length).fill(0.0)
                        if(is_sparse) {
                            for(let i=1; i<inflated.byteLength; i+=(4 + 4)) {
                                let index = dataView.getInt32(i, true)
                                array[index] = dataView.getFloat32(i+4, true)
                            }
                        } else {
                            for(let i=0; i<r.length; ++i) {
                                array[i] = dataView.getFloat32(1 + i*4, true)
                            }
                        }
                    } catch (e) {
                        throw Error('Format not recognized')
                    }
                    matrixLoaders[r.id].set({data: array})
                } catch(e) {
                    matrixLoaders[r.id].set({error: e})
                }
            }
        }
    }

    row.subscribe(async (newRow) => {
        if(newRow === undefined) return
        console.log(Object.keys(matrixLoaders).filter(k => matrixLoaders[k].subscriberCount() > 0))
        update(newRow, _data, Object.keys(matrixLoaders).filter(k => matrixLoaders[k].subscriberCount() > 0))
        _row = newRow
    })

    return {
        data, metadata, progress, row,
        getMatrixStore: (dataset, matrix) => matrixLoaders[dataset + ':' + matrix]
    }
}

export { createCore }