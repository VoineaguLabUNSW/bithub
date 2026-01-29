<script>
    import { setContext } from 'svelte';
    import { createCore } from '../lib/stores/core.js';
    import { base } from '$app/paths';
    import { createPaletteParam, createIntParam, createBoolParam } from '../lib/stores/param';
    import { primary, paletteColors, groupPaletteColors, gradientColors } from '../lib/utils/colors'
    import './../../node_modules/@fortawesome/fontawesome-free/css/all.min.css';
    import '../app.css';

    const url = `${base}/metadata.json` // 'http://localhost:5501/pipeline/output/metadata.json';
    setContext('core', createCore(url)); 
    
    
    setContext('displaySettings', {
            colorRange: createPaletteParam('colorRange', gradientColors, 3, true),
            colorPrimary: createPaletteParam('colorPrimary', [primary[500]], 1, true),
            colorWay: createPaletteParam('colorWay', paletteColors, undefined, true),
            groupColorWay: createPaletteParam('groupColorway', groupPaletteColors, undefined, true),
            exportWidth: createIntParam('exportWidth', 800, true),
            exportHeight: createIntParam('exportHeight', 600, true),
            alwaysApplyColorWay: createBoolParam('alwaysApplyColorWay', false, true),
        }
    )
</script>

<slot/>