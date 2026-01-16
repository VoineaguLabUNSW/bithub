function withoutNullsStr(str) {
    return typeof str == 'string' ? str.replace(/\0/g, '') : str;
}

function withoutNulls(arr) {
    return typeof arr[0] == 'string' ? arr.map(v => withoutNullsStr(v)) : arr;
}

function findMatchesSorted(arrays, searches) {
    searches = searches.filter(s => s.length).map(s => s.toUpperCase())
    let ret = [];
    for(const [arrIndex, arr] of arrays.entries()) {
        const searchIndices = new Map(searches.map((v, i) => [v, i]))
        for(let rowIndex=0; rowIndex<arr.length; ++rowIndex) {
            const searchIndex = searchIndices.get(withoutNullsStr(arr[rowIndex]))
            if(searchIndex !== undefined) {
                ret[searchIndex] = {arrIndex, searchIndex, rowIndex}
            }
        }
    }
    return ret.filter(v => v !== undefined)
}

export { withoutNulls, withoutNullsStr, findMatchesSorted}