import { derived } from 'svelte/store';

function createMetadataStore(core) {
    return derived([core.data, core.customs], ([$data, $customs]) => {
        const metadataColumnReaders = {};
        for(const h of $data.value.get('metadata').keys) {
            metadataColumnReaders[h] = {
                ...$data.value.get('metadata/' + h + '/samples').attrs, //order, type (optional)
                sampleNames: $data.value.get('metadata/' + h + '/sample_names').value,
                matrixNames: $data.value.get('metadata/' + h + '/matrices').keys.filter(m => !m.endsWith('_pvalues')),
                getMatrixStore: $data.rowStreams,
                getColumn: (colHeading) => {
                    const sRoot = $data.value.get('metadata/' + h + '/samples/' + colHeading)
                    return {values: sRoot.value, attrs: sRoot.attrs}
                },
            }
        }
        for(let cd of Object.values($customs)) {
            metadataColumnReaders[cd.name] = cd.metadataColumnReader;
        }
        return {readers: metadataColumnReaders}
    });
}

export { createMetadataStore };
