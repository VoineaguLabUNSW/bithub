<script>
import { setContext } from 'svelte';
import { createCore } from '../lib/stores/core.js';
import './../../node_modules/@fortawesome/fontawesome-free/css/all.min.css'
import '../app.css';

const url = 'https://d33ldq8s2ek4w8.cloudfront.net/combined/metadata.json'
setContext('core', createCore(url)); 
</script>

<slot/>