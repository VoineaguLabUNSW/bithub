<script>
    import { Button, Dropdown, Search} from 'flowbite-svelte';

    export let selected;

    export let groups;
    export let title = '';
    export let placeholder = 'Select...';

    let open = false;
    let filter = '';
    let disabled = !groups || Array.from(groups.values()).reduce((acc, arr) => acc + arr.length, 0) == 0
    $: if(!open) filter = '';
  </script>
  
<div class='w-48 flex flex-col items-stretch'>
    <div class='text-sm ml-2'>{title}</div>
    <Button disabled={disabled} color="light">{$selected?.name || placeholder}<i class='fas fa-angle-down pl-2 text-gray-200'/></Button>
    <Dropdown placement='down' bind:open class="overflow-y-auto px-3 pb-3 text-sm h-44 divide-y divide-gray-100">
    <div slot="header" class="p-3">
        <Search placeholder='Filter...' bind:value={filter} size="md" />
    </div>
    {#each [...groups].map(([key, values]) => [key, values.filter(v => v.name.toLowerCase().includes(filter.toLowerCase()))]).filter(([_, values]) => values.length) as [key, values]}
        {key}
        {#each values as v }
            {#key v}
                {#if v.disabled}
                    <li class="rounded p-2 bg-gray-100 dark:hover:bg-gray-600">{v.name}</li>
                {:else if v.id == $selected?.id}
                    <li class="rounded p-2 bg-gray-100 dark:bg-gray-600">{v.name}</li>
                {:else}
                    <li class="rounded p-2 hover:bg-gray-100 dark:hover:bg-gray-600" on:click={() => {selected.set(v); open=false}}>{v.name}</li>
                {/if}
            {/key}
        {/each}
    {/each}
    </Dropdown>
</div>