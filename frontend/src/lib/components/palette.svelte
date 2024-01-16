<script context="module">
    import "@melloware/coloris/dist/coloris.css";
    import Coloris from "@melloware/coloris";
    Coloris.init();
</script>

<script>
    import { onMount } from 'svelte';
    import { writable } from 'svelte/store'

    export let palette = writable([]);
    let container;
    
    onMount(() => {
        Coloris({el: '.picker', alpha: false});
        return Coloris.close
    })
</script>

<style>
    :global(.picker-container .clr-field button) {
        width: 100%;
        height: 100%;
        border-radius: 4px;
    }
</style>

<div class="picker-container flex flex-wrap items-center gap-2" bind:this={container}>
    {#each $palette as p}
            {#key "{i}-{p}"}
                <input on:change={() => palette.set(Array.from(container.querySelectorAll('.picker')).map(e => e.value))} type="text" value={p} class="picker w-2 h-2 border-0 cursor-pointer">
            {/key}
    {/each} 
</div>
