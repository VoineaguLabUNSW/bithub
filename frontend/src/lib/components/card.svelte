<script>
    export let title, description, icon, href;
</script>

<a href="{href}" class="p-4 w-96 button">
    <div class="transition ease-in-out delay-15 flex rounded-lg h-full dark:bg-gray-800 bg-white-400 p-8 shadow-md hover:shadow-lg flex-col border-solid border-[0.5px] border-gray-300">
        <div class="flex items-center mb-3">
            <h2 class="text-black dark:text-white text-lg font-medium">{title}</h2>
            <div
                class="w-8 h-8 ml-3 inline-flex items-center justify-center rounded-full text-white flex-shrink-0">
                <i class="{icon} dark:text-white text-black"></i>
            </div>
        </div>
        <div class="flex flex-col justify-between flex-grow">
            <p class="leading-relaxed text-base text-black dark:text-white-300">
                {description}
            </p>
        </div>
    </div>
</a>