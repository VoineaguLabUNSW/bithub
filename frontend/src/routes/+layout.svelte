<script>
    import { setContext } from 'svelte';
    import { createCore } from '../lib/stores/core.js';
    import { base } from '$app/paths';
    import './../../node_modules/@fortawesome/fontawesome-free/css/all.min.css';
    import '../app.css';

    const url = `${base}/metadata.json`/*'http://localhost:5501/metadata.json'*/;
    setContext('core', createCore(url)); 
</script>

<slot/>