<script>
    import { Drawer } from 'flowbite-svelte';
    import { sineIn } from 'svelte/easing';
    import { writable, get } from "@square/svelte-store";
    import debounce from '../../utils/debounce'
    import Plotly from 'plotly.js-dist-min'

    export let plotlyArgs;

    const CONTROLS_WIDTH = 300;
    const TRANSITION_PARAMS = { x: 50, duration: 250, easing: sineIn };

    let plotContainer = writable(undefined)
    let isHovering = false;
    let toggleOn = writable()
    let hoverOn = writable();

    let firstRender = true;
    $: {
        if($plotlyArgs && $plotContainer) {
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
                    click: () => toggleOn.set(!get(toggleOn))
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
                    click: () => hoverOn.set(!get(hoverOn))
                    
                }]];

            Plotly.react($plotContainer, $plotlyArgs.plotData,
                { 
                    autosize: true,
                    margin: { t: 0 },
                    showlegend: false,
                    ...($plotlyArgs.layout || {})
                }, {
                    responsive: true, 
                    displaylogo: false, 
                    modeBarButtons: modeBarButtons,
                    ...($plotlyArgs.config || {})
                }
            );

            if(firstRender) {
                toggleOn.set(false)
                hoverOn.set(true)
                firstRender = false
            }
        }
    }

    plotContainer.subscribe((pc) => {
        if(!pc) return
        pc.onmouseleave = () => isHovering = false;
        pc.onmousemove = function(e) {
            const plotRect = pc.getBoundingClientRect();
            const thresholdX = (plotRect.width - CONTROLS_WIDTH);
            const positionX = e.clientX - plotRect.left;
            if(!isHovering && (positionX - 100) > thresholdX) isHovering = true;
            else if(isHovering && (positionX < thresholdX)) isHovering = false;
        }
    });

    $: document.querySelector('[data-attr="sidebar_hover"]')?.classList.toggle('active', $hoverOn)
    $: document.querySelector('[data-attr="sidebar_toggle"]')?.classList.toggle('active', $toggleOn)
    toggleOn.subscribe(v => v && hoverOn.set(false))
    hoverOn.subscribe(v => v && toggleOn.set(false))
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

<div id='plot-container' class="relative h-full w-full overflow-x-hidden" bind:this={$plotContainer}>
    <Drawer placement="right" activateClickOutside={false} backdrop={false} transitionType="fly" transitionParams={TRANSITION_PARAMS} hidden={!($toggleOn || ($hoverOn && isHovering))} id="sidebar1" class='absolute bg-gray-50/90' style='width:{CONTROLS_WIDTH}px'>
        <slot name='controls'></slot>
    </Drawer>
</div>
