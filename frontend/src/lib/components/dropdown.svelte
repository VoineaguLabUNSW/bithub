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
        <Search autofocus placeholder='Filter...' bind:value={filter} size="md" />
    </div>
    {#each [...groups].map(([key, values]) => [key, values.filter(v => key.toLowerCase().includes(filter.toLowerCase()) || v.name.toLowerCase().includes(filter.toLowerCase()))]).filter(([_, values]) => values.length) as [key, values]}
        <div class='p-2 text-gray-400'>{key}</div>
        {#each values as v }
            {#key v}
                {#if v.disabled}
                    <li class="rounded pl-4 p-2 bg-gray-100 dark:hover:bg-gray-600">{v.name}</li>
                {:else if v.id == $selected?.id}
                    <li class="rounded pl-4 p-2 bg-gray-100 dark:bg-gray-600">{v.name}</li>
                {:else}
                    <li class="rounded pl-4 p-2 hover:bg-gray-100 dark:hover:bg-gray-600" on:click={() => {selected.set(v); open=false}}>{v.name}</li>
                {/if}
            {/key}
        {/each}
    {/each}
    </Dropdown>
</div>