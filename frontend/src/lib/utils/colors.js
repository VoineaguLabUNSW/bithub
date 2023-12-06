import chroma from "chroma-js";

// Editable constants
const gradient_colors = ['#ffa500', 'gray', '#941a6c']
const gradient_stops = [-3, 0, 3]
const primary = {
    '50': '#fff8eb',
    '100': '#feeac7',
    '200': '#fdd28a',
    '300': '#fcbb4d',
    '400': '#fbab24',
    '500': '#f59e0b',
    '600': '#d98b06',
    '700': '#b47409',
    '800': '#92610e',
    '900': '#78510f',
    '950': '#452c03',
}

// Helper functions
function gradientHelper(colors, stops) {
    const norm = (v, min, max) => (v - min) / (max-min)
    const clamp = (v, min, max) => Math.max(min, Math.min(v, max))

    const scales = colors.slice(1).map((_, i) => chroma.scale([colors[i], colors[i+1]]))
    const gradientRange = [stops[0], stops[stops.length-1]]
    const gradientCSS = stops.map((s, i) => `${colors[i]} ${norm(s, ...gradientRange)*100}%`).flat()

    function toColorScale(v) {
        let i=0;
        v = clamp(v, ...gradientRange)
        for(; stops[i+1]<v; i++) continue;
        v = norm(v, stops[i], stops[i+1])
        return scales[i](v).hex();
    }

    return { toColorScale, gradientCSS, gradientRange }
}

const { toColorScale, gradientCSS, gradientRange } = gradientHelper(gradient_colors, gradient_stops);

export { primary, toColorScale, gradientCSS, gradientRange}