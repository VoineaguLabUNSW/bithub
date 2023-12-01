<script>
    import { getContext, onMount } from "svelte";
    import { Progressbar } from 'flowbite-svelte';
    import { fade } from 'svelte/transition';
    import { sineOut } from 'svelte/easing';
    const { progress, data } = getContext('core');

    let isFirstRender=true
    onMount(() => isFirstRender=false)
</script>

<div class="sticky top-0 h-0">
    {#if !$data?.value && !isFirstRender}
        <div transition:fade={{ delay: 500 }}>
            <Progressbar animate progress={$progress} size="h-1" color="red" easing={sineOut} tweenDuration={1500}/>
        </div>
    {/if}
</div>
  
