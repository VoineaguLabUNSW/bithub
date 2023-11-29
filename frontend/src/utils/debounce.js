export default function debounce(callback, wait, starve=false) {
    let pending = null;
    let last = null
    return (...args) => {
        const now = Date.now()
        if(starve || (now - (last + wait)) < wait) window.clearTimeout(pending);
        pending = window.setTimeout(() => {last=now; callback.apply(null, args)}, wait);
    };
}
