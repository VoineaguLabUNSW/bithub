import { goto } from '$app/navigation';
import { page } from '$app/stores';
import { derived, get } from 'svelte/store';

function createParam(param, defaultVal='', fn=v => v, preventSideEffects=false) {
    const store = derived(page, ($page)=> $page && fn($page.url.searchParams.get(param)) || defaultVal, defaultVal)
    return {
      set: v => {
        console.log('setting', v)
        let lastPage = get(page)
        if(lastPage.url.searchParams.get(param) == v) return;
        let query = new URLSearchParams(lastPage.url.searchParams.toString());
        query.set(param, v);
        goto(`${lastPage.url.pathname}?${query.toString()}`,  preventSideEffects && { keepFocus: true, noScroll: true});
      },
      subscribe: store.subscribe
    }
}

function createIntParam(param, defaultVal=1, preventSideEffects=false) {
    return createParam(param, defaultVal, parseInt, preventSideEffects)
}

function createListParam(param, sep=',', preventSideEffects=false) {
    return createParam(param, [], (v) => v && v.split(sep), preventSideEffects)
}

export { createIntParam, createParam, createListParam}
  