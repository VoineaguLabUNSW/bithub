function withoutNullsStr(str) {
    return str.replace(/\0.*$/g, '')
}

function withoutNulls(arr) {
    return typeof arr[0] == 'string' ? arr.map(v => withoutNullsStr(v)) : arr;
}

export { withoutNulls, withoutNullsStr }