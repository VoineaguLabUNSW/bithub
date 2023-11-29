<script>
    import { getContext } from "svelte";
    import { onMount } from 'svelte';
    import { Drawer, Toggle } from 'flowbite-svelte';
    import Dropdown from '../components/dropdown.svelte'
    import { sineIn } from 'svelte/easing';
    import { writable, get } from "@square/svelte-store";
    import Plotly from 'plotly.js-dist-min'

    export let filteredStore;

    let plotContainer = writable(undefined)
    let datasetsAll;
    const drawerWidth = 300;

    let datasetsSelect1 = writable('')
    let datasetsSelect2 = writable('')

    let isHovering = false;

    let isToggled = writable()
    let canHover = writable();

    isToggled.subscribe(v => v && canHover.set(false))
    canHover.subscribe(v => v && isToggled.set(false))

    const transitionParamsRight = { x: 50, duration: 250, easing: sineIn };

    const { data } = getContext('core')

    // Initial data parse
    filteredStore.subscribe(fs => {
        if(fs && !datasetsAll) {
            const { headingGroups } = fs
            datasetsAll = headingGroups.get('Datasets')
            datasetsSelect1.set(datasetsAll[0])
            datasetsSelect2.set(datasetsAll[1])
        }
    })

    let ro = undefined

    // Main plotting loop
    $: {
        if($filteredStore && $plotContainer && $datasetsSelect1 && $datasetsSelect2 && datasetsAll) {
            console.log('plotting...')
            let modeBarButtons = [[ "autoScale2d", "pan2d",
                { 
                    // https://fontawesome.com/icons/sliders
                    name: 'Sidebar Toggle',
                    icon: {
                        path:  'M0 416c0 17.7 14.3 32 32 32l54.7 0c12.3 28.3 40.5 48 73.3 48s61-19.7 73.3-48L480 448c17.7 0 32-14.3 32-32s-14.3-32-32-32l-246.7 0c-12.3-28.3-40.5-48-73.3-48s-61 19.7-73.3 48L32 384c-17.7 0-32 14.3-32 32zm128 0a32 32 0 1 1 64 0 32 32 0 1 1 -64 0zM320 256a32 32 0 1 1 64 0 32 32 0 1 1 -64 0zm32-80c-32.8 0-61 19.7-73.3 48L32 224c-17.7 0-32 14.3-32 32s14.3 32 32 32l246.7 0c12.3 28.3 40.5 48 73.3 48s61-19.7 73.3-48l54.7 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-54.7 0c-12.3-28.3-40.5-48-73.3-48zM192 128a32 32 0 1 1 0-64 32 32 0 1 1 0 64zm73.3-64C253 35.7 224.8 16 192 16s-61 19.7-73.3 48L32 64C14.3 64 0 78.3 0 96s14.3 32 32 32l86.7 0c12.3 28.3 40.5 48 73.3 48s61-19.7 73.3-48L480 128c17.7 0 32-14.3 32-32s-14.3-32-32-32L265.3 64z',
                        width: 512, height: 512
                    },
                    attr: 'sidebar_toggle',
                    toggle: true,
                    click: () => {isToggled.set(!get(isToggled));}
                },
                {
                    // https://fontawesome.com/icons/arrow-pointer
                    name: 'Sidebar Hover',
                    icon: {
                        path: 'M0 55.2V426c0 12.2 9.9 22 22 22c6.3 0 12.4-2.7 16.6-7.5L121.2 346l58.1 116.3c7.9 15.8 27.1 22.2 42.9 14.3s22.2-27.1 14.3-42.9L179.8 320H297.9c12.2 0 22.1-9.9 22.1-22.1c0-6.3-2.7-12.3-7.4-16.5L38.6 37.9C34.3 34.1 28.9 32 23.2 32C10.4 32 0 42.4 0 55.2z',
                        width: 512, height: 512
                    },
                    attr: 'sidebar_hover',
                    toggle: true,
                    click: () => {canHover.set(!get(canHover))}
                    
                }]];

            const inds = [$datasetsSelect1, $datasetsSelect2].map(h => $filteredStore.headings.indexOf(h))
            const cols = inds.map(i => $filteredStore.columns[i])
            const filteredInd = inds.map((col_i, d_i) => $filteredStore.results.map(row_i => cols[d_i][row_i]))
            const filteredNames = $filteredStore.results.map(row_i => $filteredStore.columns[1][row_i])
            Plotly.react( $plotContainer, 
                [
                    {
                        mode: 'markers',
                        type: 'scattergl',
                        name: 'all',
                        x: cols[0],
                        y: cols[1],
                        hoverinfo: 'skip',
                        marker : {color: 'rgb(219, 219, 219)'}
                    },
                    {
                        mode: 'markers',
                        type: 'scattergl',
                        name: '',
                        x: filteredInd[0],
                        y: filteredInd[1],
                        marker : {color: 'rgb(196, 89, 59)'},
                        text: filteredNames
                    }
                ], 
                { 
                    autosize: true,
                    margin: { t: 0 },
                    showlegend: false,
                }, {
                    responsive: true, 
                    displaylogo: false, 
                    modeBarButtons: modeBarButtons,
                }
            );

            isToggled.set(false)
            canHover.set(true)
        }
    }

    plotContainer.subscribe((pc) => {
        if(!pc) return
        pc.onmouseleave = () => isHovering = false
        pc.onmousemove = function(e) {
            const plotRect = pc.getBoundingClientRect();
            const thresholdX = (plotRect.width - drawerWidth);
            const positionX = e.clientX - plotRect.left ;
            if(!isHovering && (positionX - 100) > thresholdX) isHovering = true
            else if(isHovering && (positionX < thresholdX)) isHovering = false
        }

        const debounce = (callback, wait, starve=false) => {
            let pending = null;
            let last = null
            return (...args) => {
                const now = Date.now()
                if(starve || (now - (last + wait)) < wait) window.clearTimeout(pending);
                pending = window.setTimeout(() => {last=now; callback.apply(null, args)}, wait);
            };
        }
        ro = new ResizeObserver(debounce((_) => Plotly.Plots.resize(pc), 100)).observe(pc)
    });

    $: document.querySelector('[data-attr="sidebar_hover"]')?.classList.toggle('active', $canHover)
    $: document.querySelector('[data-attr="sidebar_toggle"]')?.classList.toggle('active', $isToggled)
</script>

<!--Force plotly controls to top middle, fix tailwindcss incompatibility (https://github.com/plotly/plotly.js/issues/5828) -->
<style>
    :global(.modebar) {
        right: 0px !important;
        left: 0px !important;
        display: flex;
        justify-content: center;

    }
    :global(.js-plotly-plot .plotly .modebar svg) {
        display: inline;
    }

    :global(.modebar-btn > .icon) {
        height: 2em;
        width: 2em;
    }

    :global(div.plotly-notifier) {
        visibility: hidden;
    }
</style>

<div class="relative h-[calc(75vh-200px)] overflow-x-hidden" bind:this={$plotContainer}>
    <Drawer placement="right" activateClickOutside={false} backdrop={false} transitionType="fly" transitionParams={transitionParamsRight} hidden={!($isToggled || ($canHover && isHovering))} id="sidebar1" class='absolute bg-gray-50/90' style='width:{drawerWidth}px'>
        <div class="flex justify-between">
            <h5 id="drawer-label" class="inline-flex items-center mb-4 text-base font-semibold text-gray-500 dark:text-gray-400">
                <i class='fas fa-gears m-2'/>Datasets
            </h5>
        </div>
        <p class="mb-6 text-sm text-gray-500 dark:text-gray-400">
            Select from different datasets to compare z-scores for any number of search results.
        </p>

        <div class='w-48 flex flex-col items-stretch gap-3'>
            <Dropdown title='Dataset 1' selected={datasetsSelect1} groups={new Map([['', datasetsAll]])}/>
            <Dropdown title='Dataset 2' selected={datasetsSelect2} groups={new Map([['', datasetsAll]])}/>
        </div>
    </Drawer>
</div>

