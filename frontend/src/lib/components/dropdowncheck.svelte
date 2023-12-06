<script>
    import { Button, Dropdown, Checkbox, Search} from 'flowbite-svelte';
    import { ChevronDownSolid } from 'flowbite-svelte-icons';

    export let groups;
    export let title = 'Select...';
    export let disabled = [];
    export let selected = [];
    export let mainClass = '';
    export let color = 'light';

    let open = false;
    
    let filter = '';
    $: if(!open) filter = '';
</script>
  
<Button class={mainClass} color={color}>{title}<ChevronDownSolid class="w-3 h-3 ml-2 text-gray-200 dark:text-white" /></Button>
<Dropdown bind:open class="overflow-y-auto px-3 pb-3 text-sm h-44 divide-y divide-gray-100">
    <div slot="header" class="p-3">
        <Search placeholder='Filter...' bind:value={filter} size="md" />
    </div>
    {#each [...groups].map(([key, values]) => [key, values.filter(v => v.toLowerCase().includes(filter.toLowerCase()))]).filter(([_, values]) => values.length) as [key, values]}
        {key}
        {#each values as v }
            {#key v}
            <li class="select-none rounded p-2 hover:bg-gray-100 dark:hover:bg-gray-600">
                <Checkbox on:change={() => selected.set($selected)} id={v} disabled={disabled.includes(v)} group={$selected} value={v}>{v}</Checkbox>
            </li>
            {/key}
        {/each}
    {/each}
</Dropdown>