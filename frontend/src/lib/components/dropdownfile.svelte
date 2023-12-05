<script>
    import { Button, Dropdown, Toggle, Fileupload } from 'flowbite-svelte';
    import { ChevronDownSolid } from 'flowbite-svelte-icons';
    
    export let title = '';
    export let help = ''
    export let mainClass = ''

    export let files;
    export let active;
    export let error;

    let open;
</script>
  
<Button class={mainClass} color="light">
    <span class='whitespace-nowrap overflow-hidden text-ellipsis'>{($files?.length && $active && !error) ? $files[0].name : title}</span>
    <ChevronDownSolid class="w-3 h-3 ml-2 text-gray-200 dark:text-white" />
</Button>
<Dropdown bind:open class=" overflow-y-auto px-3 pb-3 text-sm">
    <div slot="header" class="p-3">
        <Fileupload bind:files={$files} size="md" />
    </div>
    {#key $files?.length }
        <Toggle disabled={!$files?.length} bind:checked={$active}>{(!$files?.length ? 'No file selected' : `Filter using ${$files[0].name}`)}</Toggle>
        <div class='pt-4'>
            <p>{help}</p>
            <p class='text-red-600'>{error || ''}</p>
        </div>
    {/key}
</Dropdown>