<script>
    import { base } from '$app/paths';
    import ChatFigure from './chatfigure.svelte';
    import ChatTable from './chattable.svelte';
    import ChatBar from './chatbar.svelte';

    import { renderMarkdown } from '$lib/utils/markdown';

    export let message;

    // Assistant output is markdown — headings, emphasis, lists — so it is
    // parsed and sanitised (see utils/markdown.js) rather than shown verbatim.
    // User and error text stays plain: neither should be able to inject HTML.
</script>

{#if message.role === 'user'}
    <div class="flex justify-end">
        <div class="max-w-[75%] bg-primary-500 text-white rounded-2xl rounded-br-sm
                    px-4 py-2.5 text-sm shadow-sm">{message.content}</div>
    </div>

{:else if message.role === 'error'}
    <div class="flex gap-2.5 text-sm bg-red-50 border border-red-200
                rounded-xl px-4 py-3">
        <i class="fas fa-circle-exclamation text-red-500 mt-0.5"></i>
        <span class="text-red-900">{message.content}</span>
    </div>

{:else}
    <div class="flex gap-3">
        <div class="w-7 h-7 shrink-0 rounded-full bg-primary-500 text-white
                    grid place-items-center text-xs mt-0.5">
            <i class="fas fa-comment-dots"></i>
        </div>

        <div class="min-w-0 flex-1 space-y-3">
            <div class="chat-prose min-w-0">
                {@html renderMarkdown(message.content)}
            </div>

            {#if message.datasetsUnavailable?.length}
                <div class="flex gap-2 text-[13px] bg-amber-50 border border-amber-200
                            rounded-lg px-3.5 py-2.5">
                    <i class="fas fa-triangle-exclamation text-amber-500 mt-0.5"></i>
                    <span class="text-amber-900">
                        Not included:
                        {#each message.datasetsUnavailable as u, i}
                            <strong>{u.dataset}</strong> ({u.reason}){i < message.datasetsUnavailable.length - 1 ? ', ' : '.'}
                        {/each}
                    </span>
                </div>
            {/if}

            <!-- Tools return either a table or a proportion bar; `type`
                 discriminates. Unknown types are skipped rather than crashing
                 the message, so a new backend renderable degrades gracefully
                 against an older frontend. -->
            {#each message.tables as renderable}
                {#if renderable.type === 'stacked_bar'}
                    <ChatBar bar={renderable}/>
                {:else}
                    <ChatTable table={renderable}/>
                {/if}
            {/each}

            {#each message.figures as figure}
                <ChatFigure {figure}/>
            {/each}

            {#if message.literature?.error}
                <div class="flex gap-2 text-[13px] bg-gray-50 border border-gray-200
                            rounded-lg px-3.5 py-2.5">
                    <i class="fas fa-book text-gray-400 mt-0.5"></i>
                    <span class="text-gray-600">{message.literature.error}</span>
                </div>
            {/if}

            {#if message.literature?.results?.length}
                <div class="space-y-1.5">
                    {#each message.literature.results as paper}
                        <a href={paper.url} target="_blank" rel="noopener"
                           class="block border border-gray-200 rounded-lg px-3.5 py-2
                                  hover:border-primary-300 hover:bg-primary-50 transition">
                            <div class="text-[13px] text-gray-800 leading-snug">{paper.title}</div>
                            <div class="text-xs text-gray-500 mt-0.5">{paper.source}</div>
                        </a>
                    {/each}
                </div>
            {/if}

            {#if message.lastGene}
                <a href="{base}/search?terms={message.lastGene}"
                   class="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full
                          border border-primary-200 text-primary-700
                          hover:bg-primary-50 transition">
                    <i class="fas fa-arrow-right text-[10px]"></i>
                    Open {message.lastGene} in BITHub
                </a>
            {/if}

            {#if message.toolsUsed?.length}
                <div class="text-[11px] text-gray-400">
                    {message.datasetsUsed?.join(' + ')} · grounded via
                    {[...new Set(message.toolsUsed)].join(', ')}
                    {#if message.elapsedMs}· {(message.elapsedMs / 1000).toFixed(1)}s{/if}
                </div>
            {/if}
        </div>
    </div>
{/if}
