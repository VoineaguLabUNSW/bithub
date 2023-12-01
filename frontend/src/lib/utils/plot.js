
function getPlotEmpty(message) {
    return {
        plotData: [],
        layout: {
            autosize: true,
            xaxis: {
                zeroline:false,
                linecolor: 'black',
                linewidth: 1,
                mirror: true,
                showticklabels:false
            }, 
            yaxis: {
                zeroline: false, 
                linecolor: 'black',
                linewidth: 1,
                mirror: true,
                showticklabels:false
            },
            annotations: [{
                x: 0.5,
                y: 0.5,
                xref: 'paper',
                yref: 'paper',
                text: message,
                font: {
                    color: "grey",
                    size: 12
                },
                showarrow: false
            }]
        },
        config: {
            responsive: true,
            displaylogo: false,
            staticPlot: true,
        }
    }
}

function getPlotViolin(heading, subHeading, data, xName, yName, orderX, groupLabelsX, groupSizesX, orderZ) {
    
}

export { getPlotEmpty }