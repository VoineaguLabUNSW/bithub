import chroma from "chroma-js";

// Editable constants
const gradientColors = ['#0b06b8', '#ffffff', '#b80641'];
const gradientStops = [-2, 0, 3]
const primary = {
        DEFAULT: 'cf648a',
        '50': '#fcf4f5',
        '100': '#f9eaee',
        '200': '#f4d7e0',
        '300': '#ebb6c7',
        '400': '#df8fa9',
        '500': '#cf648a',
        '600': '#b94574',
        '700': '#9b3560',
        '800': '#822f55',
        '900': '#702b4c',
        '950': '#3d1426',
}

// https://sashamaps.net/docs/resources/20-colors/
const paletteColors = ['#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080','#000000']

const groupPaletteColors = ['#fc03f0', 'blue']

// Helper functions
function gradientHelper(colors, stops) {
    const norm = (v, min, max) => (v - min) / (max-min)
    const clamp = (v, min, max) => Math.max(min, Math.min(v, max))

    const scales = colors.slice(1).map((_, i) => chroma.scale([colors[i], colors[i+1]]))
    const gradientRange = [stops[0], stops[stops.length-1]]
    const gradientCSS = stops.map((s, i) => `${colors[i]} ${norm(s, ...gradientRange)*100}%`).flat()
    const gradientPairs = stops.map((s, i) => [norm(s, ...gradientRange), colors[i]])

    function toColorScale(v) {
        let i=0;
        v = clamp(v, ...gradientRange)
        for(; stops[i+1]<v; i++) continue;
        v = norm(v, stops[i], stops[i+1])
        return scales[i](v).hex();
    }

    return { toColorScale, gradientCSS, gradientRange, gradientPairs }
}

const { toColorScale, gradientCSS, gradientRange, gradientPairs } = gradientHelper(gradientColors, gradientStops);

export { primary, toColorScale, gradientCSS, gradientRange, gradientColors, gradientPairs, paletteColors, groupPaletteColors}