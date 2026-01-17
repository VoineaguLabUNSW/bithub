<script>
import '../../../node_modules/tocbot/dist/tocbot.css'
import * as tocbot from 'tocbot';
import { onMount, getContext } from 'svelte'
import { Breadcrumb, BreadcrumbItem } from 'flowbite-svelte';
import { base } from '$app/paths';
import { primary } from '../../lib/utils/colors'

import Footer from '../../lib/components/footer.svelte'
import ProgressHeader from '../../lib/components/progress.svelte'

import videoUsingSearch from '../../lib/assets/1 Using Search.webm'
import videoNavigatingResults1 from '../../lib/assets/2 Navigating Results 1.webm'
import videoNavigatingResults2 from '../../lib/assets/3 Navigating Results 2.webm'
import videoTranscriptExpression from '../../lib/assets/4 Transcript Expression.webm'

const { metadata } = getContext('core')

let tocElement;
let contentElement;

// NEW: UI state
let showIntroMore = false;

// NEW: derived dataset groupings + stats
$: metaFiles = $metadata?.value?.meta_files ?? [];
// Heuristic: bulk sample counts are small; snRNA-seq "samples" here are actually cells and are much larger
$: bulkFiles = metaFiles.filter((d) => (Number(d.samples) || 0) < 10000);
$: snFiles   = metaFiles.filter((d) => (Number(d.samples) || 0) >= 10000);

$: bulkSampleTotal = bulkFiles.reduce((acc, d) => acc + (Number(d.samples) || 0), 0);
$: snCellTotal     = snFiles.reduce((acc, d) => acc + (Number(d.samples) || 0), 0);

// --- Metadata dictionary table state ---
let dictRows = [];
let dictLoading = true;
let dictError = null;

$: groupedRows = (() => {
  const map = new Map();

  for (const r of dictRows ?? []) {
    const key = `${r.Metadata}|||${r.Description}|||${r.Type}`;
    if (!map.has(key)) {
      map.set(key, {
        Metadata: r.Metadata,
        Description: r.Description,
        Type: r.Type,
        Datasets: []
      });
    }
    const entry = map.get(key);
    if (r.Dataset && !entry.Datasets.includes(r.Dataset)) {
      entry.Datasets.push(r.Dataset);
    }
  }

  // Optional: sort datasets within each row
  for (const v of map.values()) v.Datasets.sort();

  // Optional: sort rows by Metadata
  return Array.from(map.values()).sort((a, b) =>
    String(a.Metadata).localeCompare(String(b.Metadata))
  );
})();

// Step 4: dataset legend toggle + filtering

// All dataset names present in the raw dictionary
$: allDatasets = Array.from(
  new Set((dictRows ?? []).map((r) => r.Dataset).filter(Boolean))
).sort();

// Which datasets are currently shown (by default: all)
let activeDatasets = new Set();

// Initialize activeDatasets once when datasets first appear
$: if (allDatasets.length && activeDatasets.size === 0) {
  activeDatasets = new Set(allDatasets);
}

function toggleDataset(ds) {
  const next = new Set(activeDatasets);
  if (next.has(ds)) next.delete(ds);
  else next.add(ds);
  activeDatasets = next;
}

// Filter grouped rows based on activeDatasets
$: filteredGroupedRows = (groupedRows ?? [])
  .map((r) => ({
    ...r,
    Datasets: (r.Datasets ?? []).filter((ds) => activeDatasets.has(ds))
  }))
  .filter((r) => r.Datasets.length > 0);


onMount(async () => {
  // 1) init TOC
  tocbot.init({
    tocElement,
    contentElement,
    headingSelector: 'h3, h4, h5',
    hasInnerContainers: true,
  });

  // 2) load metadata dictionary
  try {
    const res = await fetch('/api/metadata');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    dictRows = await res.json();
  } catch (e) {
    dictError = e.message ?? String(e);
  } finally {
    dictLoading = false;
  }

  // cleanup
  return () => tocbot.destroy();
});
</script>

<style>
  /* Tocbot: active link indicator (uses CSS var; falls back if missing) */
  :global(.is-active-link::before) {
    background-color: var(--toc-color, #122c48);
  }

  /* ---- Metadata table ---- */
  .meta-table-wrap {
    max-height: 380px;
    overflow: auto;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    background: #ffffff;
    margin-top: 12px;
  }

  .meta-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.95rem;
  }

  .meta-table th,
  .meta-table td {
    padding: 10px 12px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: top;
    text-align: left;
  }

  .meta-table thead th {
    position: sticky;
    top: 0;
    z-index: 2;
    background: #ffffff;
    border-bottom: 1px solid #e5e7eb;
  }

  .meta-table tbody tr:hover {
    background: #f8fafc;
  }

  /* Keep the chip column from getting too wide/tall-looking */
  .meta-table td:last-child {
    min-width: 220px;
  }

  /* ---- Dataset chips ---- */
  .chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.85rem;
    line-height: 1.2;
    border: 1px solid #e5e7eb;
    background: #f8fafc;
    white-space: nowrap;
  }

  /* Dataset-specific colors */
  .chip-BrainSeq {
    background: #fee2e2;
    border-color: #fecaca;
  }
  .chip-BrainSpan {
    background: #dcfce7;
    border-color: #bbf7d0;
  }
  .chip-GTEx {
    background: #dbeafe;
    border-color: #bfdbfe;
  }
  .chip-HDBR {
    background: #f3e8ff;
    border-color: #e9d5ff;
  }

.legend {
  margin-top: 10px;
  margin-bottom: 10px;
}

.legend-title {
  display: inline-block;
  margin-bottom: 6px;
  font-weight: 600;
}

.chip-btn {
  cursor: pointer;
}

.chip-off {
  opacity: 0.35;
  filter: grayscale(1);
}

</style>


<ProgressHeader/>
<div class='m-12 mt-4 mb-[10%]' style="--toc-color: {primary[500]}">
  <div class='pb-4'>
    <Breadcrumb aria-label="Home breadcrumbs">
      <BreadcrumbItem href="{base}" home>Home</BreadcrumbItem>
      <BreadcrumbItem>Datasets</BreadcrumbItem>
    </Breadcrumb>
  </div>

  <div class='grid grid-flow-col gap-10'>
    <!-- TOC -->
    <div class="col-span-1 select-none h-fit sticky top-24 pt-2 w-48">
      <div bind:this={tocElement}></div>
    </div>

    <!-- CONTENT -->
    <div bind:this={contentElement} class="col-span-4 max-w-4xl mx-auto">
      <h1 class='text-4xl font-sans "Helvetica Neue" mb-5'>
        <span>Brain Integrative Transcriptome Hub </span><span class='text-gray-400'>(BITHub)</span>
      </h1>
      <h2 class='text-3xl font-sans "Helvetica Neue" mb-4'>User Guide and Analysis</h2>


      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 my-6">
        <div class="rounded-lg border bg-white px-3 py-2 text-sm">
          <div class="font-semibold text-gray-900">Gene queries</div>
          <div class="text-gray-500">Search by symbol or Ensembl ID</div>
        </div>
        <div class="rounded-lg border bg-white px-3 py-2 text-sm">
          <div class="font-semibold text-gray-900">Cross-dataset</div>
          <div class="text-gray-500">Compare expression across studies</div>
        </div>
        <div class="rounded-lg border bg-white px-3 py-2 text-sm">
          <div class="font-semibold text-gray-900">Region & developmental stage</div>
          <div class="text-gray-500">Filter by brain context</div>
        </div>
        <div class="rounded-lg border bg-white px-3 py-2 text-sm">
          <div class="font-semibold text-gray-900">Genome view</div>
          <div class="text-gray-500">Transcript-level browsing</div>
        </div>
      </div>

      <h3 id='introduction' class='text-2xl font-sans "Helvetica Neue" mb-2'>1. Introduction</h3>

      <!-- NEW: collapsible intro -->
      <p class="mb-2 text-gray-700">
        Brain Integrative Transcriptome Hub (BITHub) is a web resource for exploring gene expression across human brain transcriptomic datasets.
        It integrates 5 large-scale bulk RNA-seq studies and 3 single-nucleus RNA-seq studies spanning brain regions and developmental stages.
        <button
          class="ml-2 underline text-primary-600"
          on:click={() => (showIntroMore = !showIntroMore)}
          aria-expanded={showIntroMore}
        >
          {showIntroMore ? 'Show less' : 'Read more'}
        </button>
      </p>

      {#if showIntroMore}
        <p class="mb-5 text-gray-700">
          Datasets are provided with curated metadata, inferred cell-type composition, and variance-aware analyses. Interactive visualisations allow users to examine gene expression patterns across datasets and biological contexts in a consistent and accessible way.
        </p>
      {:else}
        <div class="mb-5"></div>
      {/if}

      <h3 id='datasets' class='text-2xl font-sans "Helvetica Neue" mb-2'>2. Datasets</h3>

      <!-- NEW: stats grid -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
        <div class="rounded-lg border bg-white px-3 py-2">
          <div class="text-xs text-gray-500">Bulk datasets</div>
          <div class="text-lg font-semibold">{bulkFiles.length}</div>
        </div>
        <div class="rounded-lg border bg-white px-3 py-2">
          <div class="text-xs text-gray-500">Bulk samples</div>
          <div class="text-lg font-semibold">{bulkSampleTotal.toLocaleString()}</div>
        </div>
        <div class="rounded-lg border bg-white px-3 py-2">
          <div class="text-xs text-gray-500">snRNA-seq datasets</div>
          <div class="text-lg font-semibold">{snFiles.length}</div>
        </div>
        <div class="rounded-lg border bg-white px-3 py-2">
          <div class="text-xs text-gray-500">Cells (snRNA-seq)</div>
          <div class="text-lg font-semibold">{snCellTotal.toLocaleString()}</div>
        </div>
      </div>

      <p class="mt-4 text-gray-700">
        Download links below provide access to the processed files used by BITHub.
      </p>

      {#if metaFiles.length}

        <!-- NEW: grouped tables -->
        <h4 class="text-xl font-sans mt-8 mb-2">Bulk RNA-seq datasets</h4>
        <div class="relative overflow-x-auto shadow-md sm:rounded-lg my-4">
          <table class="w-full text-sm text-left rtl:text-right text-gray-600 dark:text-gray-400">
            <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
              <tr>
                {#each ['Dataset', 'Downloads', 'Samples'] as h}
                  <th scope="col" class="px-6 py-3">{h}</th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each bulkFiles as d}
                <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                  <th scope="row" class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white">
                    {d.name}
                  </th>
                  <td class="px-6 py-4">
                    <a class="underline text-primary-600 mr-4" href={d.matrix_url}>Expression</a>
                    <a class="underline text-primary-600" href={d.meta_url}>Metadata</a>
                  </td>
                  <td class="px-6 py-4">
                    {Number(d.samples || 0).toLocaleString()}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>

        <h4 class="text-xl font-sans mt-10 mb-2">Single-nucleus RNA-seq datasets</h4>
        <div class="relative overflow-x-auto shadow-md sm:rounded-lg my-4">
          <table class="w-full text-sm text-left rtl:text-right text-gray-600 dark:text-gray-400">
            <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
              <tr>
                {#each ['Dataset', 'Downloads', 'Cells'] as h}
                  <th scope="col" class="px-6 py-3">{h}</th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each snFiles as d}
                <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                  <th scope="row" class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white">
                    {d.name}
                  </th>
                  <td class="px-6 py-4">
                    <a class="underline text-primary-600 mr-4" href={d.matrix_url}>Expression</a>
                    <a class="underline text-primary-600" href={d.meta_url}>Metadata</a>
                  </td>
                  <td class="px-6 py-4">
                    {Number(d.samples || 0).toLocaleString()}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>

      {/if}

      <h3 id='tutorial' class='text-2xl font-sans "Helvetica Neue" my-4'>3. Tutorial</h3>
      <p>
        Analyze spatiotemporal properties of your gene of interest
      </p>

      <h5 id='tutorial-submit' class='text-xl font-sans "Helvetica Neue" my-2'>i. Submit your query</h5>
      <p class='ml-4'>
        Use the search bar in the home-page by either by entering the HGNC-approved gene symbol or Ensembl IDs. Users can also input multiple genes separated by a comma. Files containing comma separated values (.csv) containing a list of genes can also be uploaded and searched for. You can use the input example genes to gain familiarity with the expected format.
      </p>

      <video class="w-5/6 py-5 m-auto select-none"
        src={videoUsingSearch}
        loop
        autoplay
        muted
      />

      <h5 id='tutorial-navigate' class='text-xl font-sans "Helvetica Neue" my-2'>ii. Navigating your results</h5>
      <p class='ml-4'>
        Once a query has been sent to the interface, you will be directed to the main page with the results. The gene or genes of interest will be shown in a table with their Ensembl ID, Gene Symbol and a heatmap. The heatmap denotes the relative expression of the gene amongst datasets and if that gene is present in the given dataset. The user can then navigate directly to the corresponding gene page and explore its expression properties for each dataset. Click on the modal to investigate gene expression properties of a specific gene.
      </p>

      <video class="w-5/6 py-5 m-auto select-none"
        src={videoNavigatingResults1}
        loop
        autoplay
        muted
      />
      <video class="w-5/6 py-5 m-auto select-none"
        src={videoNavigatingResults2}
        loop
        autoplay
        muted
      />

      <h5 id='tutorial-visualize' class='text-xl font-sans "Helvetica Neue" my-2'>iii. Visualize your results</h5>
      <div class='ml-4'>
        <p>BITHub displays the following panels with interactive visualisations: </p>
        <ul class='list-disc ml-8'>

            <li>
            <p>Gene Exp Across Datasets</p>
            <p>
                This panel summarises overall gene expression in the human brain. 
                Selecting any two datasets generates a scatterplot of z-score–transformed mean log₂ expression values for genes shared between the datasets, with each point representing a gene and the queried gene highlighted in pink.
                 Z-scores can also be viewed for specific brain regions or developmental stages using the subset menu. When interpreting these plots, note that datasets differ in developmental coverage, regional sampling, and expression quantification methods (see Dataset description)
            </p>
          </li>
          <li>
           <p>Gene Exp Across Variables (Bulk) </p>
           <p>This panel enables gene-level exploration of expression patterns of the aggregated datasets.
            Gene expression values can be visualized in relation to a range of biological and technical metadata variables, including phenotype (e.g. age, sex), sample characteristics, and sequencing metrics. 
            Users may also restrict analyses to specific brain regions using the Select Brain Region menu. 

            Visualizations adapt to metadata type, using box plots for categorical variables and scatterplots for continuous variables, with ANOVA or correlation statistics displayed on the x-axis and interactive zooming and filtering enabled.
            A data dictionary and the availability of metadata variables across curated datasets are shown in the table below.
           </p>
           <div class="legend">
                <span class="legend-title">Datasets:</span>
                <div class="chip-row">
                    {#each allDatasets as ds}
                    <button
                        type="button"
                        class={"chip chip-btn chip-" + ds.replace(/\s+/g, '') + (activeDatasets.has(ds) ? "" : " chip-off")}
                        on:click={() => toggleDataset(ds)}
                        aria-pressed={activeDatasets.has(ds)}
                        title={activeDatasets.has(ds) ? "Click to hide" : "Click to show"}
                    >
                        {ds}
                    </button>
                    {/each}
                </div>
                </div>

            {#if dictLoading}
                <p>Loading metadata dictionary…</p>
            {:else if dictError}
                <p style="color: red;">Failed to load metadata: {dictError}</p>
            {:else}
                <div class="meta-table-wrap">
                    <table class="meta-table">
                    <thead>
                        <tr>
                        <th>Metadata</th>
                        <th>Description</th>
                        <th>Type</th>
                        <th>Dataset</th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each filteredGroupedRows as r}
                            <tr>
                            <td>{r.Metadata}</td>
                            <td>{r.Description}</td>
                            <td>{r.Type}</td>
                            <td>
                                <div class="chip-row">
                                {#each r.Datasets as ds}
                                    <span class={"chip chip-" + ds.replace(/\s+/g, '')}>
                                    {ds}
                                    </span>
                                {/each}
                                </div>
                            </td>
                            </tr>
                        {/each}
                        </tbody>
                    </table>
                </div>
                {/if}
          </li>
        <li>
           <p>Drivers of variation </p>
           <p>This panel displays the metadata variables that contribute to expression variation for the selected gene across datasets, estimated using variancePartition (Hoffman & Schadt). 
            Interactive charts show the fraction of variance explained in each dataset. 
            “Unknown” indicates that variancePartition results are unavailable for that gene due to filtering.
           </p>
          </li>

             <li>
           <p>Gene Exp Across Variables (Single Cell) </p>
           <p>This panel enables gene-level exploraotion of expression patterns of the aggregated datasets.
            Gene expression values can be visualisation in relation to a range of biological and technical metadata variables, including phenotype (e.g. age, sex), sample characteristics, and sequencing metrics. 
            Users may also restrict analyses to specific brain regions using the Select Brain Region menu. 
            Visualisatiçns adapt to metadata type, using box plots for categorical variables and scatterplots for continuous variables, with ANOVA or correlation statistics displayed on the x-axis and interactive zooming and filtering enabled.
            A data dictionary and the availability of metadata variables across curated datasets are shown in the table below.
           </p>
          </li>
          <li>
            Transcript Exp
          </li>

          <video class="w-5/6 py-5 m-auto select-none"
            src={videoTranscriptExpression}
            loop
            autoplay
            muted
          />

          

          <li>
            <p>Genome Browser</p>
            <p>
                This panel provides a genome browser view displaying genomic coordinates and annotations from Ensembl, RefSeq, and FANTOM5. Users can navigate genomic regions and expand individual transcripts to examine isoform-specific structure and expression.
            </p>
        </ul>
      </div>
    </div>
  </div>
</div>

<Footer metadata={metadata}/>