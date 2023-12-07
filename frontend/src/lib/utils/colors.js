import chroma from "chroma-js";

// Editable constants
const gradientColors = ['#0b06b8', '#ffffff', '#b80641']
const gradientStops = [-2, 0, 3]
const primary = {
    DEFAULT: '#e74c4c',
    '50': '#fdf3f3',
    '100': '#fde3e3',
    '200': '#fbcdcd',
    '300': '#f8a9a9',
    '400': '#ef6060',
    '500': '#e74c4c',
    '600': '#d32f2f',
    '700': '#b12424',
    '800': '#932121',
    '900': '#7a2222',
    '950': '#420d0d',
}

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

export { primary, toColorScale, gradientCSS, gradientRange, gradientColors, gradientPairs}