import { createRowWriter } from '../utils/save'
import { withoutNullsStr } from './hdf5';

function getZipped(columns) {
    let keys = Object.keys(columns);
    return columns[keys[0]].map((_, i) => keys.reduce((acc, curr) => {acc[curr] = columns[curr][i]; return acc}, {}))
}

function getColumnDownloader(heading, data, xName, yName, zName) {
    return () => {
        const onlyDefined = (arr) =>  arr.filter(v => v !== undefined).map(v => withoutNullsStr(v))
        const csv = createRowWriter(heading.toLowerCase().replaceAll(' ', '_') + '.csv', ',')
        csv.write(onlyDefined(['', yName, xName, zName]))
        for(let d of data) csv.write(onlyDefined([d.name, d.y, d.x, d.z]))
        csv.close()
    }
}

function getTablDownloader(heading, headingsX, headingsY, values) {
    return () => {
        const csv = createRowWriter(heading.toLowerCase().replaceAll(' ', '_') + '.csv', ',')
        csv.write(['', ...headingsX])
        for(let [i, h] of headingsY.entries()) csv.write([h, ...values[i]])
        csv.close()
    }
}

function getOrderIndexed(arr, order, unknown_name='Unknown', unknown_index=Infinity) {
    const ret = new Map(order.map((x, i) => [x, {index: i, seen: false}]));
    arr.forEach(v => {
        const entry = ret.get(v)
        if(entry) entry.seen = true
        else ret.set(v, {index: ret.size, seen: true})
    });
    const unknown = ret.get(unknown_name)
    if(unknown) unknown.index = unknown_index
    return ret
}

function getPlotEmpty(message) {
    return {
        plotData: [],
        layout: {
            autosize: true,
            xaxis: { showticklabels:false }, 
            yaxis: { showticklabels:false },
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
        },
    }
}

function getPlotScatter(heading, data, xName, yName, zName, orderZ) {
    const [hasZ, hasName] = [data[0].z !== undefined, data[0].name !== undefined];
    const orderZDic = hasZ ? getOrderIndexed(data.map(d => d.z), orderZ || []) : new Map()
    const seenZ = [...orderZDic.entries()].filter(([_, v]) => v.seen).map(([k, _]) => k)

    const plotData = []
    if(hasZ) {
        for(let cat of seenZ) {
            let filtered = data.filter(d => d.z == cat);
            if (!filtered.length) continue
            plotData.push({
                type: "scattergl",
                mode: 'markers+text',
                name: cat,
                hovertext: hasName ? data.map(d => d.name) : undefined,
                hoverinfo: "x+y+text+name",
                hoverlabel: {
                    bgcolor: 'white',
                    font: {color: 'black'}
                },
                x: filtered.map(d => d.x),
                y: filtered.map(d => d.y),
                showlegend: true,
            });
        }
    } else {
        plotData.push({
            type: "scattergl",
            mode: "markers",
            hovertext: hasName ? data.map(d => d.name) : undefined,
            hoverinfo: "x+y+text",
            hoverlabel: {
                bgcolor: 'white',
                font: {color: 'black'}
            },
            x: data.map(d => d.x),
            y: data.map(d => d.y),
            showlegend: false,
        })
    }

    return { plotData, 
        layout: { 
            title: {
                text: heading,
                font: { family: "Times New Roman", size: 20 },
            },
            xaxis: {
                title: {
                    text: xName,
                    font: { family: 'Times New Roman', size: 18, color: '#7f7f7f' }
                },
            },
            yaxis: {
                title: {
                    text: yName,
                    font: { family: 'Times New Roman', size: 18, color: '#7f7f7f' }
                }
            },
        },
        downloadCSV: getColumnDownloader(heading, data, xName, yName, zName)
    }
}

function getPlotViolinBasic(heading, data, xName, yName, zName, orderX, orderZ, groupLabelsX, groupSizesX) {
    const hasZ = data[0].z !== undefined 
    const orderXDic = getOrderIndexed(data.map(d => d.x), orderX || [])
    const orderZDic = hasZ ? getOrderIndexed(data.map(d => d.z), orderZ || []) : new Map()
    const seenX = [...orderXDic.entries()].filter(([_, v]) => v.seen).map(([k, _]) => k)

    data.sort((a,b) => (orderZDic.get(a.z)?.index - orderZDic.get(b.z)?.index) || (orderXDic.get(a.x)?.index - orderXDic.get(b.x)?.index))

    const groupShapes = [];
    const groupAnnotations = [];

    if(groupSizesX) {
        // Reduce group sizes for unseen values
        const xToGroup = {}
        for(let group=0, groupStart=0; group<groupSizesX.length; groupStart+=groupSizesX[group++]) {
            for(let i=0; i<groupSizesX[group]; ++i) {
                xToGroup[orderX[groupStart+i]] = group
            }
        }
        orderX.forEach(x => !orderXDic.get(x)?.seen && (groupSizesX[xToGroup[x]] -= 1))

        // Create labelled group boxes with dividers
        const groupColorsX = ['#fc03f0', 'blue']
        for(let group=0, prevStart=0, nextStart=groupSizesX[0]; group<groupSizesX.length; ++group, prevStart=nextStart, nextStart+=groupSizesX[group]) {
            if(prevStart === nextStart) continue

            groupShapes.push({
                type: 'rect',
                xref: 'x',
                yref: 'paper',
                x0: prevStart-0.5,
                y0: 0,
                x1: nextStart-0.5,
                y1: 1,
                fillcolor: groupColorsX[group % groupColorsX.length],
                opacity: 0.03,
                line: { width: 1}
            })

            groupAnnotations.push({
                text: groupLabelsX[group],
                xref: 'x',
                yref: 'paper',
                x: nextStart-0.5,
                xanchor: 'right',
                y: 1,
                yanchor: 'top',
                showarrow: false,
                opacity: 0.25,
                borderwidth: 10,
            });

            if(nextStart < seenX.length) {
                groupShapes.push({
                    type: 'line',
                    xref: 'x',
                    yref: 'paper',
                    x0: nextStart-0.5,
                    y0: 0,
                    x1: nextStart-0.5,
                    y1: 1,
                    line: {
                        color: 'black',
                        width: 2,
                        dash: 'dashdot'
                    }
                });
            }            
        }
    }

    // Create violins
    //Since it's sorted by (Z || X), changes in Z are the major group dividers
    const plotData = [];
    const range = [0, 1]
    for(let i=1; i<data.length; ++i) {
        const isLast = (i == (data.length-1));
        const didChange = data[i-1].z != data[i].z

        if(!didChange || isLast) {
            ++range[1] 
        }

        if((didChange || isLast) && ((range[1] - range[0]) || groupSizesX)) {
            const dataRange = data.slice(...range)
            plotData.push({
                type: 'violin',
                // NaN for each possible category forces plotly to create empty spaces for them
                x: (groupSizesX ? seenX : []).concat(dataRange.map(d => d.x)),
                y: (groupSizesX ? new Array(seenX.length).fill(NaN) : []).concat(dataRange.map(d => d.y)),
                hovertext: (groupSizesX ? new Array(seenX.length).fill('') : []).concat(dataRange.map(d => d.name)),
                hoverinfo: "y+text",
                hoverlabel: {
                    bgcolor: 'white',
                    font: {color: 'black'}
                },
                legendgroup: data[i-1].z,
                name: data[i-1].z,
                box: { visible: true },
                meanline: { visible: true },
            });
            range[0] = i;
        }
    }
    return { 
        plotData, 
        layout: {
            violinmode: hasZ && 'group',
            title: {
                text: heading,
                font: { family: "Times New Roman", size: 20 }
            },
            xaxis: {
                title: {
                    text: xName,
                    font: { family: 'Times New Roman', size: 18, color: '#7f7f7f' }
                },
            },
            yaxis: {
                title: {
                    text: yName,
                    font: { family: 'Times New Roman', size: 18, color: '#7f7f7f' }
                }
            },
            shapes: groupShapes,
            annotations: groupAnnotations,
            legend: { x: 1, y: 0.5 }
        },
        downloadCSV: getColumnDownloader(heading, data, xName, yName, zName)
    }
}

export { getPlotEmpty, getPlotViolinBasic, getPlotScatter, getColumnDownloader, getZipped, getTablDownloader }