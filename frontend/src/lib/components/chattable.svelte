<script>
    import { Table, TableBody, TableBodyCell, TableBodyRow,
             TableHead, TableHeadCell } from 'flowbite-svelte';

    /** Render-ready table from the chat backend. */
    export let table;

    function fmt(v, format) {
        if (v === null || v === undefined || v === '') return '—';
        if (typeof v !== 'number') return v;
        if (format === 'pct') return `${(v * 100).toFixed(1)}%`;
        if (format === '2dp') return v.toFixed(2);
        if (format === '3dp') return v.toFixed(3);
        return String(v);
    }
</script>

<div class="border border-gray-200 rounded-xl overflow-hidden bg-white">
    {#if table.title}
        <div class="px-4 py-2.5 border-b border-gray-100 text-xs font-semibold
                    text-gray-600 uppercase tracking-wide">{table.title}</div>
    {/if}

    <div class="overflow-x-auto">
        <Table striped={false}>
            <TableHead>
                {#each table.columns as col}
                    <TableHeadCell class={col.align === 'right' ? 'text-right' : ''}>
                        {col.label}
                    </TableHeadCell>
                {/each}
            </TableHead>
            <TableBody>
                {#each table.rows as row, i}
                    <TableBodyRow class={i === table.highlight_row ? 'bg-primary-50' : ''}>
                        {#each row as cell, j}
                            <TableBodyCell
                                class="{table.columns[j].align === 'right'
                                        ? 'text-right tabular-nums' : ''}
                                       {i === table.highlight_row
                                        ? 'font-medium text-primary-900' : ''}">
                                {fmt(cell, table.columns[j].format)}
                                {#if i === table.highlight_row && j === row.length - 1
                                     && table.highlight_note}
                                    <span class="text-primary-700 text-xs font-medium"
                                    >← {table.highlight_note}</span>
                                {/if}
                            </TableBodyCell>
                        {/each}
                    </TableBodyRow>
                {/each}
            </TableBody>
        </Table>
    </div>

    {#if table.footnote}
        <div class="px-4 py-2 text-xs text-gray-500 border-t border-gray-100">
            {table.footnote}
        </div>
    {/if}
</div>
