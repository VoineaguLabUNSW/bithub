<script>
    import { getContext } from "svelte";
    import { Progressbar } from 'flowbite-svelte';
    import { fade } from 'svelte/transition';
    import { sineOut } from 'svelte/easing';
    const { progress, data } = getContext('core')
</script>


<div class="sticky top-0 h-0">
    {#if !$data?.value}
        <div transition:fade={{ delay: 500 }}>
            <Progressbar animate progress={$progress} size="h-1" color="red" easing={sineOut} tweenDuration={1500} precision={2}/>
        </div>
    {/if}
</div>
  
