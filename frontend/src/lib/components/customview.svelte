<script>
    import { Fileupload, Label, Button } from 'flowbite-svelte';
    let value;
</script>

<div>
    <div class='mb-4'>
        <p>Adds local columns and charts, no data is shared with BITHub.</p>
        <p>Contact our lab for additions to the core database.</p>
    </div>

    <Label class="space-y-2 mb-4">
        <span>Load Expression Matrix</span>
        <Fileupload bind:value />
    </Label>

    <Label class="space-y-2 mb-4">
        <span>Load Metadata</span>
        <Fileupload bind:value />
    </Label>

    <div class='flex flex-col items-center'>
        <Button disabled color='light'>Add<i class='mx-2 fas fa-upload'/></Button>
    </div>
</div>