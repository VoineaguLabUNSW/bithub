//Just create this at the source you coward
/*
// Add dataset -> 
function createMetadataStores(customDatasets) {
    return derived(customDatasets, ($customDatasets) => {
        const metadataColumnReaders = {}
        for(let cd of $customDatasets) {
            metadataColumnReaders[cd.name] = ({
                ...cd,
                getColumn: (colHeading) => ({values: cd.metadata[colHeading]}),
            });
        }
        return {readers: metadataColumnReader}
    });
}
*/

import { derived } from 'svelte/store';

function createMetadataStore(core) {
    return derived(core.data, ($data) => {
        const metadataColumnReaders = {};
        for(const h of $data.value.get('metadata').keys) {
            metadataColumnReaders[h] = {
                ...$data.value.get('metadata/' + h + '/samples').attrs, //order, type (optional)
                sampleNames: $data.value.get('metadata/' + h + '/sample_names').value,
                matrixNames: $data.value.get('metadata/' + h + '/matrices').keys,
                getMatrixStore: $data.rowStreams,
                getColumn: (colHeading) => {
                    const sRoot = $data.value.get('metadata/' + h + '/samples/' + colHeading)
                    return {values: sRoot.value, attrs: sRoot.attrs}
                },
            }
        }
        for(const group of $data.value.get('panels').keys) {
            for(const h of $data.value.get('panels/' + group).keys) {
                metadataColumnReaders[h].group = group
            }
        }
        return {readers: metadataColumnReaders}
    });
}

export { createMetadataStore };
