<script>
    import { fade } from 'svelte/transition';
    import { getContext } from 'svelte'
    const { metadata } = getContext('core')
</script>

<footer class="h-[8%] fixed bottom-0 left-0 z-20 w-full p-4 bg-zinc-800 border-t border-gray-200 shadow md:flex md:items-center md:justify-between md:p-6 dark:bg-gray-800 dark:border-gray-600">
    <div class="w-full mx-auto max-w-screen-xl p-4 md:flex md:items-center md:justify-between">
        <span class="text-sm text-gray-500 sm:text-center dark:text-gray-400">
            <p class="flex">
                <span>Developed at <a target="_blank" href="https://www.babs.unsw.edu.au/voineagu-lab" class="text-red-600">Voineagu Lab</a>
                </span>
                {#if $metadata?.value}
                    <span in:fade={{ delay: 500 }}>, data last updated {$metadata.value.last_updated}<strong id="last_updated"></strong>.</span>
                {/if}
            </p>
        </span>
        <ul class="flex flex-wrap items-center mt-3 text-sm font-medium text-gray-500 dark:text-gray-400 sm:mt-0">
            <li>
                <a rel="noopener" target="_blank" href="https://github.com/VoineaguLabUNSW/BITHub"><i class="fa-brands fa-github text-3xl"/></a>
            </li>
        </ul>
    </div>
</footer>