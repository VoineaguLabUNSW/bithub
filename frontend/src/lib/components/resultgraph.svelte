<script>
    import { getContext } from "svelte";
    import Dropdown from './dropdown.svelte'
    import { paginate, LightPaginationNav } from 'svelte-paginate'
    import chroma from "chroma-js";
    import { Button } from 'flowbite-svelte';
    import { writable, derived } from 'svelte/store';

    export let filteredStore;

    const { data } = getContext('core')
</script>