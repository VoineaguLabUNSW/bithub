<script>
    import { Button, Dropdown, Search} from 'flowbite-svelte';

    export let groups;
    export let title = '';
    export let disabled = [];
    export let selected;

    let open = false;
    let filter = '';
    $: if(!open) filter = '';

    if(!groups) groups = new Map([['First', ['one', 'two', 'three', 'four']], ['Second', ['five']]]);
    if(Array.isArray(groups)) groups = new Map([['', groups]]);
  </script>
  
<div class='w-48 flex flex-col items-stretch'>
    <div class='text-sm ml-2'>{title}</div>
    <Button color="light">{$selected || 'Select...'}<i class='fas fa-angle-down pl-2 text-gray-200'/></Button>
    <Dropdown placeholder='wow' placement='down' bind:open class="overflow-y-auto px-3 pb-3 text-sm h-44 divide-y divide-gray-100">
    <div slot="header" class="p-3">
        <Search placeholder='Filter...' bind:value={filter} size="md" />
    </div>
    {#each [...groups].map(([key, values]) => [key, values.filter(v => v.toLowerCase().includes(filter.toLowerCase()))]).filter(([_, values]) => values.length) as [key, values]}
        {key}
        {#each values as v }
            {#key v}
                {#if disabled.includes(v)}
                    <li class="rounded p-2 bg-gray-100 dark:hover:bg-gray-600">{v}</li>
                {:else if v == $selected}
                    <li class="rounded p-2 bg-gray-100 dark:bg-gray-600">{v}</li>
                {:else}
                    <li class="rounded p-2 hover:bg-gray-100 dark:hover:bg-gray-600" on:click={() => {selected.set(v); open=false}}>{v}</li>
                {/if}
            {/key}
        {/each}
    {/each}
    </Dropdown>
</div>