import { withoutNulls } from "./hdf5";
import { getZipped } from "./plot";
import { LOG_OFFSET } from "./math";
import { getPlotScatter, getPlotDistribution } from "./plot";

const SupportedCategoricalPlotTypes = ["Violin", "Box", "Bar"]
const SupportedLogTypes = ['Linear', 'Log e', 'Log 2', 'Log 10']

function createPlotlyArgsFromMetadataOptions(heading, reader, expressionData, pvalueData, datasetsSelect, matrixSelect, metadataSelect1, metadataSelect2, plotType, expressionLinearThreshold, scaleSelect, customSelect, colorWay, groupColorWay, colorPrimary, alwaysApplyColorWay) {
    let x = withoutNulls(reader.getColumn(metadataSelect1).values)
    const z = metadataSelect2 && withoutNulls(reader.getColumn(metadataSelect2).values)
    
    const names = reader.sampleNames;
    let y = expressionData.values;
    
    const isCategorical = (typeof x[0]) == 'string' || x[0] instanceof String

    const csColumn = customSelect ? withoutNulls(reader.getColumn(reader.customFilterColumn).values) : undefined;
    
    const orderX = reader.getColumn(metadataSelect1).attrs.order
    const orderZ = metadataSelect2 && reader.getColumn(metadataSelect2).attrs.order
    
    const groupSizesX = reader.getColumn(metadataSelect1).attrs.groupSizes
    const groupLabelsX = reader.getColumn(metadataSelect1).attrs.groupLabels

    const pValIdx = reader.order.indexOf(metadataSelect1);
    let headingX = "";
    if (metadataSelect2 || pvalueData === undefined) {
        headingX = metadataSelect1;
    } else {
        let statistic = pvalueData.values[2 * pValIdx].toPrecision(2);
        let pval = pvalueData.values[2 * pValIdx + 1];
        let pvalDisplay = pval < 10e-12 ? 'p<10e-12' : `p=${pval.toPrecision(2)}` // Minimum pvalue 10e-12
        let statisticName = isCategorical ? 'f' : 'r';
        let testName = isCategorical ? 'ANOVA' : 'Pearson cor';
        if (!isNaN(pval)) headingX = `${metadataSelect1} (${pvalDisplay}, ${statisticName}=${statistic}, ${testName})`;
    }

    let headingY = matrixSelect;
    const headingZ = metadataSelect2;

    // Only apply this input field when it is actually visible
    const threshold = plotType === "Bar" ? expressionLinearThreshold : 0;
    
    // Calculate % expressing/nonzero and add to x labels if required
    let zeroXCounts = {}
    if (isCategorical) {
        x.forEach((v, i) => {
            let curr = zeroXCounts[v];
            if (curr === undefined) curr = zeroXCounts[v] = [0, 0, 0];
            if (!customSelect || csColumn[i] === customSelect) {
                curr[0]++; // Track total count for each category
                if (y[i] > threshold) curr[1]++; // Track greater than threshold for each category
                if (y[i] >= 1) curr[2]++; // Track greater than 1 for each category
            }
        });
    }

    const headingMain = `${heading} - ${datasetsSelect}` + (customSelect ? ` (${customSelect})` : ``)

    if (isCategorical && plotType === "Bar") {
        // For categories, x value becomes UNIQUE categories, y value becomes % expressed
        headingY = `% ${matrixSelect} above ${threshold}`;
        let zeroXCountsEntries = Object.entries(zeroXCounts);
        let x = orderX ? orderX.filter(v => v in zeroXCounts) : Object.keys(zeroXCounts);
        let y = x.map(x => { let curr = zeroXCounts[x]; return (curr[1]/curr[0]*100); });
        set(getPlotBar(headingMain, x, y, headingX, headingY, colorPrimary[0]));
    } else {
        // Combine and apply custom filter if necessary
        let data = z ? getZipped({x, y, z, name: names}) : getZipped({x, y, name: names})
        if(customSelect) data = data.filter((d, i) => csColumn[i] == customSelect)

        // Apply scale
        if(scaleSelect != 'Linear') {
            headingY = `${headingY} (${scaleSelect})`;
            let fn = {"Log e": Math.log, "Log 2": Math.log2, "Log 10": Math.log10}[scaleSelect];
            if (fn === undefined) throw new Error("Unsupported scale: " + scaleSelect);
            data.forEach(v => v.y = fn(v.y + LOG_OFFSET));
        }

        if (isCategorical) {
            if (!["Violin", "Box"].includes(plotType)) throw new Error("Unsupported plot type: " + plotType);

            // For categories that have partial expression and at least one expression > 1.0, add suffix text
            let xSuffixes = {};
            for (const [v, curr] of Object.entries(zeroXCounts)) {
                if (curr[1] !== curr[0] && curr[2] > 0) xSuffixes[v] = ` (${(curr[1]/curr[0]*100).toFixed(2)}% expr)`       
            }
            return getPlotDistribution(headingMain, data, headingX, headingY, headingZ, orderX, orderZ, groupLabelsX, groupSizesX, xSuffixes, colorWay, groupColorWay, plotType.toLowerCase(), alwaysApplyColorWay);
        } else {
            return getPlotScatter(headingMain, data, headingX, headingY, headingZ, orderZ, {}, colorWay);
        }
    }
}

export { createPlotlyArgsFromMetadataOptions, SupportedCategoricalPlotTypes, SupportedLogTypes }