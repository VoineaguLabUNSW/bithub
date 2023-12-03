function withoutNulls(arr) {
    return typeof arr[0] == 'string' ? arr.map(v => v.replace(/\0.*$/g,'')) : arr;
}

export { withoutNulls }