<div id='post-upload'>
    <form>
        <div class='dropper-container'></div>

        <div class='control-strip'>
            <div class='primary-bar'>
                <input type='submit' value='Upload all' class='submit'/>
                <input type='button' value='Cancel' class='cancel'/>
                <span class='progress'></span>
            </div>

            <div class='batch-defaults'>
                <div class='field'>
                    <span class='field-label'>Tags for all</span>
                    <input type='text' name='all-tags' placeholder='added to every uploaded post'/>
                </div>
                <div class='field'>
                    <span class='field-label'>Safety for all</span>
                    <span class='segmented default-safety'><%
                        %><a href data-safety='safe'>Safe</a><%
                        %><a href data-safety='sketchy'>Sketchy</a><%
                        %><a href data-safety='unsafe'>Unsafe</a><%
                    %></span>
                </div>
            </div>

            <div class='upload-options'>
                <a href class='upload-options-toggle'>Upload options</a>
                <div class='upload-options-body'>
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
                </div>
            </div>
        </div>

        <div class='bulk-strip'>
            <div class='selection-bar'>
                <span class='selection-info'></span>
                <span class='selection-links'>
                    <a href class='select-all'>Select all</a>
                    <a href class='select-none'>Deselect</a>
                    <a href class='clear-list'>Clear list</a>
                </span>
            </div>

            <div class='selection-actions'>
                <span class='group'>
                    <span class='group-label'>Safety</span>
                    <span class='segmented selection-safety'><%
                        %><a href data-safety='safe'>Safe</a><%
                        %><a href data-safety='sketchy'>Sketchy</a><%
                        %><a href data-safety='unsafe'>Unsafe</a><%
                    %></span>
                </span>

                <span class='group'>
                    <span class='group-label'>Tags</span>
                    <input type='text' name='bulk-tags' placeholder='tags to add'/>
                    <a href class='bulk-tags-apply action'>Add</a>
                    <a href class='bulk-tags-filename action'>From filename</a>
                </span>

                <a href class='bulk-remove action danger'>Remove selected</a>
            </div>
        </div>

        <div class='messages'></div>

        <ul class='uploadables-container'></ul>
    </form>
</div>
