<script>
import '../../../node_modules/tocbot/dist/tocbot.css'
import * as tocbot from 'tocbot';
import { onMount, getContext } from 'svelte'
import { Breadcrumb, BreadcrumbItem } from 'flowbite-svelte';

import Footer from '../../lib/components/footer.svelte'
import ProgressHeader from '../../lib/components/progress.svelte'

import videoUsingSearch from '../../lib/assets/1 Using Search.webm'
import videoNavigatingResults1 from '../../lib/assets/2 Navigating Results 1.webm'
import videoNavigatingResults2 from '../../lib/assets/3 Navigating Results 2.webm'
import videoTranscriptExpression from '../../lib/assets/4 Transcript Expression.webm'

const { metadata } = getContext('core')

let tocElement;
let contentElement;

onMount(() => {
    tocbot.init({ tocElement, contentElement,
        headingSelector: 'h3, h4, h5',
        hasInnerContainers: true,
    });
    return () => tocbot.destroy();
})

</script>

<style>
    /* Override color of tocbot active sidebar */
    :global(.is-active-link::before) {
        background-color: #ff0000;
    }
</style>
  
<ProgressHeader/>
<div class='m-12 mt-4 mb-[10%]'>
    <div class='pb-4'>
        <Breadcrumb aria-label="Home breadcrumbs">
            <BreadcrumbItem href="/" home>Home</BreadcrumbItem>
            <BreadcrumbItem>Datasets</BreadcrumbItem>
        </Breadcrumb>
    </div>
    <div class='grid grid-flow-col gap-10'>        
        <div class="col-span-1 select-none h-fit sticky top-0 pt-2 w-48">
            <div bind:this={tocElement}></div>
        </div>

        <div bind:this={contentElement} class='col-span-4 mx-[15%]'>
            <h1 class='text-4xl font-sans "Helvetica Neue" mb-5'><span>Brain Integrative Transcriptome Hub </span><span class='text-gray-400'>(BITHub)</span></h1>
            <h2 class='text-3xl font-sans "Helvetica Neue" mb-y'>User Guide and Analysis</h2>

            <h3 id='introduction' class='text-2xl font-sans "Helvetica Neue" mb-y'>1. Introduction</h3>
            <p class='mb-5'>
                Large-scale transcriptomic consortia such as GTEx and BrainSpan have been instrumental in characterizing gene expression in the human brain across developmental stages, brain regions and cell-types. Despite this wealth of data, it is currently difficult to extract and compare gene expression information across these datasets. Their usability of publicly available gene expression data is often limited by the availability of high-quality, standardized biological phenotype and experimental condition information. Additionally, while some datasets are accompanied by data access portals (GTEx), others require significant efforts to retrieve and explore the data.
            </p>
            <p class='mb-5'>
                We introduce Brain Integrative Transcriptome Hub (BITHub), a web tool which allows integrative exploration of gene expression across 10 curated large-scale transcriptome datasets of the human brain. Our resource includes 6,933 samples from 2,933 donors spanning over 21 developmental stages and 49 different brain regions. We have performed rigorous curation and harmonization of metadata, performed cellular deconvolution, and applied a mixed-linear model framework to prioritize drivers of variation across all datasets. Users are able to explore the gene expression properties of their gene of interest through multiple interactive plots that can be populated according to user-selected brain regions, cell-types, age intervals and other technical or biological covariates of interest.
            </p>

            <h3 id='datasets' class='text-2xl font-sans "Helvetica Neue" mb-y'>2. Dataset Summary</h3>
            <p>
                We manually curated gene expression datasets of the human brain from single-nucleus and bulk RNA-seq studies. The bulk datasets total up to 5,550 samples across 31 brain structures and snRNA-seq datasets totalling up to 128, 410 cells across 9 brain cell-types.
            </p>

            <div class="relative overflow-x-auto shadow-md sm:rounded-lg my-10">
                <table class="w-full text-sm text-left rtl:text-right text-gray-500 dark:text-gray-400">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                        <tr>
                            {#each ['Dataset', 'Expression File', 'Metadata File', 'Samples'] as h}
                            <th scope="col" class="px-6 py-3">
                                {h}
                            </th>
                            {/each}
                        </tr>
                    </thead>
                    <tbody>
                        {#if $metadata?.value?.meta_files}
                            {#each $metadata.value.meta_files as meta_file}
                                <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                                    <th scope="row" class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white">
                                        {meta_file.name}
                                    </th>
                                    <td class="px-6 py-4">
                                        <a class='underline text-red-600' href={meta_file.matrix_url}>{meta_file.matrix_url.split('/').pop() || meta_file.name}</a>
                                    </td>
                                    <td class="px-6 py-4">
                                        <a class='underline text-red-600' href={meta_file.meta_url}>{meta_file.meta_url.split('/').pop() || meta_file.name}</a>
                                    </td>
                                    <td class="px-6 py-4">
                                        {meta_file.samples}
                                    </td>
                                </tr>
                            {/each}
                        {/if}
                    </tbody>
                </table>
            </div>

            <h3 id='tutorial' class='text-2xl font-sans "Helvetica Neue" my-2'>3. Tutorial</h3>
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
                <p>BITHub displays interactive plots.</p>
                <ul class='list-disc ml-8'>
                    <li>
                        Genome browser view
                    </li>
                    <li>
                        Transcript heatmaps
                    </li>
                    <video class="w-5/6 py-5 m-auto select-none"
                        src={videoTranscriptExpression}
                        loop
                        autoplay
                        muted
                    />
                    <li>
                        <p>Compare gene expression across datasets</p>
                        <p>To allow the direct comparison of gene expression across different datasets, we have provided a scatterplot listing z-score log2 mean transformed values of gene expression. This plot shows all genes in a given dataset with the gene of interest highlighted in green. Users can use this plot to determine how well a gene is expressed amongst any two datasets.</p>
                    </li>
                    <li>
                        <p>Interactive exploration of gene expression</p>
                        <p>For each gene, BITHub displays interactive plots that allow the full exploration of gene expression values (CPM/TPM/RPKM - depending on the original dataset normalization) in the bulk and single-nucleus datasets. By selecting metadata variables, users have the ability to determine how gene expression of interest varies with any metadata properties such as phenotype (e.g Age, Sex ), sample characteristic or sequencing metrics. Users also have the ability to filter the data based on region by selecting their region of interest from the ‘Select Brain Region’ or Cell-type (single-cell data) from the drop down menu.</p>
                    </li>
                    <li>
                        <p>Determine drivers of variation</p>
                        <div>
                            <p>Our database incorporates results from varianceParition into our database. The bar-graph for the variance partition shows the fraction of variance explained against selected metadata variables. The varianceParition results are currently only available for the bulk datasets and cannot be filtered by region.</p>
                            <p>If this panel shows ‘No variance partition’, this is because the gene was likely filtered out in the variancePartition analysis pipeline.</p>
                        </div>
                    </li>
                </ul>
            </div>
        </div>
    </div>
</div>

<Footer metadata={metadata}/>
