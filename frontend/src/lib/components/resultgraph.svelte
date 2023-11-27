<script>
    import { getContext } from "svelte";
    import { onMount } from 'svelte';
    import { Drawer, CloseButton, Button, Toggle } from 'flowbite-svelte';
    import Dropdown from '../components/dropdown.svelte'
    import { sineIn } from 'svelte/easing';
    import { writable, get } from "@square/svelte-store";
    import Plotly from 'plotly.js-dist-min'

    export let filteredStore;

    let plotContainer;
    let datasetsAll;
    const drawerWidth = 300;

    let datasetsSelect1 = writable('')
    let datasetsSelect2 = writable('')

    let isHovering = false;
    let isToggled = writable(true)
    let canHover = writable(false);
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

    // Main plotting loop
    $: {
        if($filteredStore && plotContainer && $datasetsSelect1 && $datasetsSelect2 && datasetsAll) {
            console.log('plotting...')
            let modeBarButtons = [[ "autoScale2d", "pan2d",
                { 
                    name: 'Lock Sidebar',
                    icon: Plotly.Icons.tooltip_compare,
                    click: () => {isToggled.set(!get(isToggled));}
                }]];

            const inds = [$datasetsSelect1, $datasetsSelect2].map(h => $filteredStore.headings.indexOf(h))
            const cols = inds.map(i => $filteredStore.columns[i])
            const filteredInd = inds.map((col_i, d_i) => $filteredStore.results.map(row_i => cols[d_i][row_i]))
            const filteredNames = $filteredStore.results.map(row_i => $filteredStore.columns[1][row_i])
            Plotly.react( plotContainer, [
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
            
            ], { 
                margin: { t: 0 },
                showlegend: false,
            }, 
                {responsive: true, displaylogo: false, modeBarButtons: modeBarButtons} );
        }
    }

    onMount(() => {
        plotContainer.onmouseleave = () => isHovering = false
        plotContainer.onmousemove = function(e) {
            const plotRect = plotContainer.getBoundingClientRect();
            const thresholdX = (plotRect.width - drawerWidth);
            const positionX = e.clientX - plotRect.left ;
            if(!isHovering && (positionX - 100) > thresholdX) isHovering = true
            else if(isHovering && (positionX < thresholdX)) isHovering = false
        }
    })
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
</style>

<div class="relative h-[600px]" bind:this={plotContainer}>
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


        <div class='flex justify-center absolute bottom-3 left-0 right-0'>
            <Toggle on:change={(e) => {canHover.set(e.target.checked)}} checked={$canHover}>Hover Mode</Toggle>
        </div>
    </Drawer>
</div>

