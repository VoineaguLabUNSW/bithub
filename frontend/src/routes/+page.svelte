<script>    
    import Card from '../lib/components/card.svelte';
    import Logo from '../lib/components/logo.svelte'
    import ProgressHeader from '../lib/components/progress.svelte'
    import { fade } from 'svelte/transition';
    import { getContext } from 'svelte';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores'
    
    const { metadata } = getContext('core')

    let inputElement = undefined;
    $: {
        if(inputElement) {
            inputElement.onkeyup = (e) => {
                if(e.key === "Enter" && inputElement.value) {
                    let query = new URLSearchParams($page.url.searchParams.toString());
                    query.set('terms', inputElement.value);
                    goto(`/search?${query.toString()}`, {replaceState: false});
                }
            }
        }
    }

    let labelElement = undefined
    $: {
        if(labelElement && $metadata?.value?.count) {
            labelElement.classList.remove('inactive')
            labelElement.setAttribute('data-domain', $metadata?.value?.count + " results");
        }
    }
</script>

<style>
    label, input {
        position: relative;
        display: block;
        font-weight: normal;
    }

    label.inactive::after, label::after {
        content: attr(data-domain);
        position: absolute;
        top: 32%;
        right: 24px;
        font-family: helvetica, sans-serif;
        font-size: 14px;
        display: inline-block;
        color: lightgrey;
        transition: opacity 1s ease-out;
    }
    label.inactive::after {
        opacity: 0;
    }

    label::after {
        opacity: 1;
    }
</style>

<ProgressHeader/>

<div class="flex justify-center mt-32">
    <div class="w-64 h-24">
        <Logo/>
    </div>
    
</div>

<div class="flex justify-center mt-10 gap-x-3">
    <label class="inactive" bind:this={labelElement}>
        <input bind:this={inputElement} class="transition ease-in-out delay-15 w-[600px] h-12 focus:border-red-600 focus:ring-red-600 caret-red-600 shadow-md hover:shadow-lg rounded-xl" type="search" placeholder='Try "MARCHF6" or "ENSG00000099785, ENSG00000136536"'/>
    </label>
    <i class="fa-solid fa-arrow-turn-up text-3xl"></i>
</div>

<div class="flex flex-wrap justify-center mt-10">
    <Card title='Learn more' href="./search" icon="fas fa-graduation-cap" description='Brain Integrative Transcriptome Hub is a web resource that allows integrative exploration of large-scale transcriptiomic studies of the human post-mortem brain.'/>
    <Card title='Advanced search' href="./search" icon="fas fa-magnifying-glass" description='Complete an advanced search...'/>
    <Card title='Load data' href="./search?load=true" icon="fas fa-file-upload" description='Load your own custom data and explore it in combination.'/>
</div>

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
