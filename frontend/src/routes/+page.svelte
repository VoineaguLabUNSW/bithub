<script>    
    import Card from '../lib/components/card.svelte';
    import Logo from '../lib/components/logo.svelte';
    import ProgressHeader from '../lib/components/progress.svelte';
    import { getContext } from 'svelte';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { base } from '$app/paths';
    import Footer from '../lib/components/footer.svelte'
    import { dev } from '$app/environment';
    import { SHOW_CHAT } from '$lib/config';

    // Ask BITHub — the in-app route at /ask. It talks to a separate FastAPI
    // service (see chatbot/README.md) that holds an Anthropic API key, so the
    // entry point stays hidden in a production build by default: the public
    // deploy must not advertise a chat that spends credits. `vite dev` always
    // shows it; to show it in a build that ships alongside the backend
    // process itself, opt in with VITE_SHOW_CHAT=true (see $lib/config).
    const showChat = dev || SHOW_CHAT;

    const { metadata } = getContext('core')

    let inputElement = undefined;
    $: {
        if(inputElement) {
            inputElement.onkeyup = (e) => {
                if(e.key === "Enter" && inputElement.value) {
                    let query = new URLSearchParams($page.url.searchParams.toString());
                    query.set('terms', inputElement.value);
                    goto(`${base}/search?${query.toString()}`, {replaceState: false});
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
            <input bind:this={inputElement} class="transition ease-in-out delay-15 w-[600px] h-12 focus:border-primary-600 focus:ring-primary-600 caret-primary-600 shadow-md hover:shadow-lg rounded-xl" type="search" placeholder='Try "MARCHF6" or "ENSG00000099785, ENSG00000136536"'/>
        </label>
        <i class="fa-solid fa-arrow-turn-up text-3xl"></i>
    </div>

    {#if showChat}
        <div class="flex justify-center mt-4">
            <!-- $page.url.search is carried through so ?source= survives the
                 hop, exactly as the Card links below do: a visitor reading a
                 non-default bundle must not be dropped onto a chat reading a
                 different one. -->
            <a href="{base}/ask{$page.url.search}"
               class="group flex items-center gap-2.5 px-5 py-2.5 rounded-full bg-white border
                      border-primary-200 shadow-sm hover:shadow-md hover:border-primary-400 transition text-sm">
                <span class="w-6 h-6 rounded-full bg-primary-500 text-white grid place-items-center text-[11px]">
                    <i class="fa-solid fa-comment-dots"></i></span>
                <span class="text-gray-700">Or ask
                    <span class="text-primary-600 font-medium">BITHub</span>
                    a question</span>
                <i class="fa-solid fa-arrow-right text-[10px] text-primary-600"></i>
                <!-- The 'dev' marker stays: locally it distinguishes a build
                     that is talking to a chat backend from one that is not.
                     No badge in production — the chat is a feature, not a
                     caveat, and 'preview' read as a disclaimer on it. -->
                {#if dev}
                    <span class="text-[10px] uppercase tracking-wide text-gray-400 border-l border-gray-200 pl-2 ml-0.5"
                    >dev</span>
                {/if}
            </a>
        </div>
    {/if}

    <div class="flex flex-wrap justify-center mt-10">
        <Card title='Learn more' href={`${base}/datasets${$page.url.search}`} icon="fas fa-graduation-cap" description='Brain Integrative Transcriptome Hub is a web resource that allows integrative exploration of large-scale transcriptiomic studies of the human post-mortem brain.'/>
        <Card title='Advanced search' href={`${base}/search${$page.url.search}`} icon="fas fa-magnifying-glass" description='Complete an advanced search...'/>
        <Card title='Load data' href={`${base}/search${$page.url.search}${$page.url.search ? '&' : '?'}open=custom`} icon="fas fa-file-upload" description='Load your own custom data and explore it in combination.'/>
    </div>
</div>
<Footer/>
