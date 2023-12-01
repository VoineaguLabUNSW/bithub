<script>
    export let visible = true;
</script>
  
<span class={visible ? 'block' : 'hidden'}>
    <slot />
</span>