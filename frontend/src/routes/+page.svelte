<script>    
    import Card from '../lib/components/card.svelte';
    import Logo from '../lib/components/logo.svelte';
    import ProgressHeader from '../lib/components/progress.svelte';
    import { getContext } from 'svelte';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { base } from '$app/paths';
    import Footer from '../lib/components/footer.svelte'
    
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

    let labelElement = undefined;
    $: {
        if(labelElement && $metadata?.value?.count) {
            labelElement.classList.remove('inactive');
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
<div class='mb-[10%]'>
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
        <Card title='Learn more' href="{base}/datasets" icon="fas fa-graduation-cap" description='Brain Integrative Transcriptome Hub is a web resource that allows integrative exploration of large-scale transcriptiomic studies of the human post-mortem brain.'/>
        <Card title='Advanced search' href="{base}/search" icon="fas fa-magnifying-glass" description='Complete an advanced search...'/>
        <Card title='Load data' href="{base}/search?open=custom" icon="fas fa-file-upload" description='Load your own custom data and explore it in combination.'/>
    </div>
</div>
<Footer/>
