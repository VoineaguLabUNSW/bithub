const count = (arr, pred) => arr.reduce((a, b) => a + (pred(b) ? 1 : 0), 0);
const sum = (arr) => arr.reduce((a, b) => a + b);
const mean = (arr) => arr.length ? sum(arr) / arr.length : 0;
const sd = (arr, arrMean) => Math.sqrt(mean(arr.map(x => Math.pow(x - arrMean, 2))))

const LOG_OFFSET=0.05

export {count, sum, mean, sd, LOG_OFFSET}