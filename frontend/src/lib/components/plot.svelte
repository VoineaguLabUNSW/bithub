<script>
    import { Drawer } from 'flowbite-svelte';
    import { sineIn } from 'svelte/easing';
    import { getContext } from 'svelte';
    import { writable, get } from "@square/svelte-store";
    import Plotly from 'plotly.js-dist-min';
    import { Tabs, TabItem, Input, Toggle } from 'flowbite-svelte';
    import Palette from '../components/palette.svelte';
    import { getFilenameFromHeading } from '../utils/plot';
    import { groupPaletteColors } from '$lib/utils/colors';
    
    export let plotlyArgs;
    
    const CONTROLS_WIDTH = 300;
    const TRANSITION_PARAMS = { x: 50, duration: 250, easing: sineIn };
    
    let { colorPrimary, colorWay, groupColorWay, colorRange, exportWidth, exportHeight, alwaysApplyColorWay } = getContext('displaySettings');

    let plotContainer = writable(undefined);
    let isHovering = true; // Show initially until cursor enters plot
    let toggleOn = writable();
    let hoverOn = writable();

    let firstRender = true;
    $: {
        if($plotlyArgs && $plotContainer) {
            const pathToIcon = (path) => ({path, width: 512, height: 512})
            const modeBarButtons = [[ "autoScale2d", "zoomIn2d", "zoomOut2d", 
                {
                    //https://fontawesome.com/icons/bezier-curve
                    name: 'Download .svg',
                    icon: pathToIcon('M368 80h32v32H368V80zM352 32c-17.7 0-32 14.3-32 32H128c0-17.7-14.3-32-32-32H32C14.3 32 0 46.3 0 64v64c0 17.7 14.3 32 32 32V352c-17.7 0-32 14.3-32 32v64c0 17.7 14.3 32 32 32H96c17.7 0 32-14.3 32-32H320c0 17.7 14.3 32 32 32h64c17.7 0 32-14.3 32-32V384c0-17.7-14.3-32-32-32V160c17.7 0 32-14.3 32-32V64c0-17.7-14.3-32-32-32H352zM96 160c17.7 0 32-14.3 32-32H320c0 17.7 14.3 32 32 32V352c-17.7 0-32 14.3-32 32H128c0-17.7-14.3-32-32-32V160zM48 400H80v32H48V400zm320 32V400h32v32H368zM48 112V80H80v32H48z'),
                    click: (gd) => Plotly.downloadImage(gd, {filename: getFilenameFromHeading($plotlyArgs.layout?.title?.text), format: 'svg', width: $exportWidth, height: $exportHeight})
                }, {
                    //https://fontawesome.com/icons/file-image
                    name: 'Download .png',
                    icon: pathToIcon('M64 0C28.7 0 0 28.7 0 64V448c0 35.3 28.7 64 64 64H320c35.3 0 64-28.7 64-64V160H256c-17.7 0-32-14.3-32-32V0H64zM256 0V128H384L256 0zM64 256a32 32 0 1 1 64 0 32 32 0 1 1 -64 0zm152 32c5.3 0 10.2 2.6 13.2 6.9l88 128c3.4 4.9 3.7 11.3 1 16.5s-8.2 8.6-14.2 8.6H216 176 128 80c-5.8 0-11.1-3.1-13.9-8.1s-2.8-11.2 .2-16.1l48-80c2.9-4.8 8.1-7.8 13.7-7.8s10.8 2.9 13.7 7.8l12.8 21.4 48.3-70.2c3-4.3 7.9-6.9 13.2-6.9z'),
                    click: (gd) => Plotly.downloadImage(gd, {filename: getFilenameFromHeading($plotlyArgs.layout?.title?.text), format: 'png', width: $exportWidth, height: $exportHeight})
                }, 
                ...($plotlyArgs.downloadCSV ? [{
                    //https://fontawesome.com/icons/file-image
                    name: 'Download .csv',
                    icon: pathToIcon('M0 64C0 28.7 28.7 0 64 0H224V128c0 17.7 14.3 32 32 32H384V304H176c-35.3 0-64 28.7-64 64V512H64c-35.3 0-64-28.7-64-64V64zm384 64H256V0L384 128zM200 352h16c22.1 0 40 17.9 40 40v8c0 8.8-7.2 16-16 16s-16-7.2-16-16v-8c0-4.4-3.6-8-8-8H200c-4.4 0-8 3.6-8 8v80c0 4.4 3.6 8 8 8h16c4.4 0 8-3.6 8-8v-8c0-8.8 7.2-16 16-16s16 7.2 16 16v8c0 22.1-17.9 40-40 40H200c-22.1 0-40-17.9-40-40V392c0-22.1 17.9-40 40-40zm133.1 0H368c8.8 0 16 7.2 16 16s-7.2 16-16 16H333.1c-7.2 0-13.1 5.9-13.1 13.1c0 5.2 3 9.9 7.8 12l37.4 16.6c16.3 7.2 26.8 23.4 26.8 41.2c0 24.9-20.2 45.1-45.1 45.1H304c-8.8 0-16-7.2-16-16s7.2-16 16-16h42.9c7.2 0 13.1-5.9 13.1-13.1c0-5.2-3-9.9-7.8-12l-37.4-16.6c-16.3-7.2-26.8-23.4-26.8-41.2c0-24.9 20.2-45.1 45.1-45.1zm98.9 0c8.8 0 16 7.2 16 16v31.6c0 23 5.5 45.6 16 66c10.5-20.3 16-42.9 16-66V368c0-8.8 7.2-16 16-16s16 7.2 16 16v31.6c0 34.7-10.3 68.7-29.6 97.6l-5.1 7.7c-3 4.5-8 7.1-13.3 7.1s-10.3-2.7-13.3-7.1l-5.1-7.7c-19.3-28.9-29.6-62.9-29.6-97.6V368c0-8.8 7.2-16 16-16z'),
                    click: () => $plotlyArgs.downloadCSV()}] : []
                ), {
                    // https://fontawesome.com/icons/sliders
                    name: 'Sidebar Toggle',
                    icon: pathToIcon('M0 416c0 17.7 14.3 32 32 32l54.7 0c12.3 28.3 40.5 48 73.3 48s61-19.7 73.3-48L480 448c17.7 0 32-14.3 32-32s-14.3-32-32-32l-246.7 0c-12.3-28.3-40.5-48-73.3-48s-61 19.7-73.3 48L32 384c-17.7 0-32 14.3-32 32zm128 0a32 32 0 1 1 64 0 32 32 0 1 1 -64 0zM320 256a32 32 0 1 1 64 0 32 32 0 1 1 -64 0zm32-80c-32.8 0-61 19.7-73.3 48L32 224c-17.7 0-32 14.3-32 32s14.3 32 32 32l246.7 0c12.3 28.3 40.5 48 73.3 48s61-19.7 73.3-48l54.7 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-54.7 0c-12.3-28.3-40.5-48-73.3-48zM192 128a32 32 0 1 1 0-64 32 32 0 1 1 0 64zm73.3-64C253 35.7 224.8 16 192 16s-61 19.7-73.3 48L32 64C14.3 64 0 78.3 0 96s14.3 32 32 32l86.7 0c12.3 28.3 40.5 48 73.3 48s61-19.7 73.3-48L480 128c17.7 0 32-14.3 32-32s-14.3-32-32-32L265.3 64z'),
                    attr: 'sidebar_toggle',
                    toggle: true,
                    click: () => toggleOn.set(!get(toggleOn))
                }, {
                    // https://fontawesome.com/icons/arrow-pointer
                    name: 'Sidebar Hover',
                    icon: pathToIcon('M0 55.2V426c0 12.2 9.9 22 22 22c6.3 0 12.4-2.7 16.6-7.5L121.2 346l58.1 116.3c7.9 15.8 27.1 22.2 42.9 14.3s22.2-27.1 14.3-42.9L179.8 320H297.9c12.2 0 22.1-9.9 22.1-22.1c0-6.3-2.7-12.3-7.4-16.5L38.6 37.9C34.3 34.1 28.9 32 23.2 32C10.4 32 0 42.4 0 55.2z'),
                    attr: 'sidebar_hover',
                    toggle: true,
                    click: () => hoverOn.set(!get(hoverOn))
                    
                }]];

            Plotly.react($plotContainer, $plotlyArgs.plotData,
                { 
                    autosize: true,
                    legend: {
                        x: 1,
                        y: 0.5
                    },
                    ...($plotlyArgs.layout || {}),
                    xaxis: {
                        automargin: true,
                        zeroline: false,
                        linecolor: 'black',
                        linewidth: 1,
                        mirror: true,
                        ...($plotlyArgs.layout?.xaxis || {}),
                    },
                    yaxis: {
                        automargin: true,
                        zeroline: false,
                        linecolor: 'black',
                        linewidth: 1,
                        mirror: true,
                        ...($plotlyArgs.layout?.yaxis || {}),
                    }
                }, {
                    responsive: true, 
                    displaylogo: false, 
                    displayModeBar: true,
                    modeBarButtons: modeBarButtons,
                    ...($plotlyArgs.config || {}),
                    staticPlot: false // Static plots break modeBarButton visible states
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
        if(!pc) return;
        function getSidebarMetrics(e) {
            const plotRect = pc.getBoundingClientRect();
            const mouseX = e.clientX + document.body.scrollLeft;
            const mouseY = e.clientY + document.body.scrollTop;
            const thresholdX = (plotRect.width - CONTROLS_WIDTH);
            const isInSidebar = (mouseX >= (plotRect.left + thresholdX) && mouseX <= plotRect.left + plotRect.width && mouseY >= plotRect.top && mouseY <= plotRect.top + plotRect.height)
            const positionX = mouseX - plotRect.left;
            return {plotRect, mouseX, mouseY, thresholdX, isInSidebar, positionX}
        }
        pc.onmouseleave = (e) => {
            if(isHovering && !getSidebarMetrics(e).isInSidebar) isHovering = false;
        }
        pc.onmousemove = function(e) {
            const m = getSidebarMetrics(e);
            if(!isHovering && (m.positionX - 100) > m.thresholdX) isHovering = true;
            else if(isHovering && m.positionX < m.thresholdX) isHovering = false;
        }
    });

    $: document.querySelector('[data-attr="sidebar_hover"]')?.classList.toggle('active', $hoverOn);
    $: document.querySelector('[data-attr="sidebar_toggle"]')?.classList.toggle('active', $toggleOn);
    toggleOn.subscribe(v => v && hoverOn.set(false));
    hoverOn.subscribe(v => v && toggleOn.set(false));
</script>

<!--Force plotly controls to top middle, fix tailwindcss incompatibility (https://github.com/plotly/plotly.js/issues/5828) -->
<style>
    :global(.modebar) {
        right: 0px !important;
        left: 50px !important;
        display: flex;
        justify-content: left;

    }
    :global(.modebar-group) {
        padding: 0px !important;
    }
    :global(.js-plotly-plot .plotly .modebar svg) {
        display: inline;
    }
    :global(.modebar-btn > .icon) {
        height: 1.5em;
        width: 1.5em;
    }
    :global(div.plotly-notifier) {
        visibility: hidden;
    }
</style>
<div id='plot-container' class="relative h-full w-full overflow-x-hidden" bind:this={$plotContainer}>
    <Drawer placement="right" activateClickOutside={false} backdrop={false} transitionType="fly" transitionParams={TRANSITION_PARAMS} hidden={!($toggleOn || ($hoverOn && isHovering))} id="sidebar1" class='absolute bg-gray-50 rounded-md outline outline-[0.1px] outline-gray-300 m-2 shadow-md backdrop-blur-md bg-white/80' style='width:{CONTROLS_WIDTH}px'>
        <Tabs style="full" defaultClass="flex rounded-lg divide-x rtl:divide-x-reverse divide-gray-200 shadow dark:divide-gray-700 gap-1">
          <TabItem class="w-full" open>
            <span slot="title">
                 <slot name='title'></slot>
            </span>
            <slot name='controls'></slot>
          </TabItem>
          <TabItem class="w-full">
            <span slot="title">
                <i class="fa-solid fa-palette"></i> Display
            </span>
            <div class="text-sm text-gray-500 dark:text-gray-400 flex flex-col items-stretch gap-3">
                <div>
                    Color Range
                    <Palette palette={colorRange}/>
                </div>
                
                <div>
                    Primary Color
                    <Palette palette={colorPrimary}/>
                </div>
                <div>
                    Colorway
                    <Palette palette={colorWay}/>
                </div>
                <div>
                    Group Colorway
                    <Palette palette={groupColorWay}/>
                </div>
                <div>
                    Export Width
                    <Input bind:value={$exportWidth} type="number" step="1" min="700"/>
                </div>
                    Export Height
                <div>
                    <Input bind:value={$exportHeight} type="number" step="1" min="450"/>
                </div> 
                <div>
                    <Toggle bind:checked={$alwaysApplyColorWay}>Apply colorway to single variable violin/box plots</Toggle>
                </div>
            </div>
          </TabItem>
        </Tabs>
    </Drawer>
</div>
