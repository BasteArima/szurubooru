<div id='post-upload'>
    <form>
        <div class='dropper-container'></div>

        <div class='control-strip'>
            <input type='submit' value='Upload all' class='submit'/>

            <span class='skip-duplicates'>
                <%= ctx.makeCheckbox({
                    text: 'Skip duplicate',
                    name: 'skip-duplicates',
                    checked: false,
                }) %>
            </span>

            <span class='always-upload-similar'>
                <%= ctx.makeCheckbox({
                    text: 'Force upload similar',
                    name: 'always-upload-similar',
                    checked: false,
                }) %>
            </span>

            <span class='auto-relate-similar'>
                <%= ctx.makeCheckbox({
                    text: 'Auto-relate similar ≥',
                    name: 'auto-relate-similar',
                    checked: false,
                }) %><%= ctx.makeNumericInput({
                    name: 'auto-relate-threshold',
                    value: 60,
                    min: 0,
                    max: 100,
                    step: 1,
                }) %><span class='suffix'>%</span>
            </span>

            <span class='pause-remain-on-error'>
                <%= ctx.makeCheckbox({
                    text: 'Pause on error',
                    name: 'pause-remain-on-error',
                    checked: true,
                }) %>
            </span>

            <input type='button' value='Cancel' class='cancel'/>

            <span class='progress'></span>

            <span class='all-tags'>
                <input type='text' name='all-tags' placeholder='Tags added to every uploaded post'/>
            </span>
        </div>

        <div class='bulk-strip'>
            <div class='selection-info'></div>
            <div class='bulk-actions'>
                <a href class='select-all'>Select all</a>
                <a href class='select-none'>None</a>
                <span class='sep'>|</span>
                <span class='bulk-safety'>Safety:
                    <a href data-safety='safe'>Safe</a>
                    <a href data-safety='sketchy'>Sketchy</a>
                    <a href data-safety='unsafe'>Unsafe</a>
                </span>
                <span class='sep'>|</span>
                <input type='text' name='bulk-tags' placeholder='tags to add'/>
                <a href class='bulk-tags-apply'>Add tags</a>
                <a href class='bulk-tags-filename'>From filename</a>
                <span class='sep'>|</span>
                <a href class='bulk-remove'>Remove</a>
                <a href class='clear-list'>Clear all</a>
            </div>
        </div>

        <div class='messages'></div>

        <ul class='uploadables-container'></ul>
    </form>
</div>
