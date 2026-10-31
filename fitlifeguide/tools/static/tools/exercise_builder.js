(function () {
    'use strict';

    function parseJson(id) {
        var node = document.getElementById(id);
        if (!node) return [];
        try {
            var value = JSON.parse(node.textContent || '[]');
            return Array.isArray(value) ? value : [];
        } catch (error) {
            return [];
        }
    }

    function formatNumber(value) {
        var number = Number(value);
        if (!Number.isFinite(number)) return '';
        if (Number.isInteger(number)) return String(number);
        return number.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
    }

    function init(builder) {
        var form = builder.closest('form');
        var rows = builder.querySelector('[data-exercise-rows]');
        var total = builder.querySelector('input[name$="-TOTAL_FORMS"]');
        var initial = builder.querySelector('input[name$="-INITIAL_FORMS"]');
        var empty = builder.querySelector('template[data-exercise-empty]');
        var addButton = builder.querySelector('[data-add-exercise]');
        var chips = builder.querySelector('[data-chips]');
        var chipList = builder.querySelector('[data-chip-list]');
        var estimateWrap = builder.querySelector('[data-estimate-wrap]');
        var estimateText = builder.querySelector('[data-estimate-text]');
        var useEstimate = builder.querySelector('[data-use-estimate]');
        var duration = form ? form.querySelector('[name="duration_minutes"]') : null;
        var live = builder.querySelector('[data-builder-live]');
        var createUrl = builder.getAttribute('data-create-url') || '';
        var maxRows = parseInt(builder.getAttribute('data-max') || '30', 10);
        var catalog = parseJson('exercise-catalog-data');
        var recent = parseJson('recent-exercises-data');
        var dragRow = null;
        var openState = null;
        var activeIndex = -1;
        var lastEstimate = null;

        if (!rows || !total || !empty) return;

        function rowNodes() {
            return Array.prototype.slice.call(rows.querySelectorAll('[data-exercise-row]'));
        }

        function field(row, name) {
            return row.querySelector('[data-field="' + name + '"]');
        }

        function rowType(row) {
            var select = field(row, 'type');
            return select && select.value ? select.value : 'strength';
        }

        function numericValue(row, name) {
            var input = field(row, name);
            if (!input || input.value === '') return null;
            var value = Number(input.value);
            return Number.isFinite(value) ? value : null;
        }

        function isBlank(row) {
            var name = field(row, 'name');
            if (name && name.value.trim()) return false;
            var numeric = ['sets', 'reps', 'weight_kg', 'seconds', 'minutes', 'distance_km'];
            return numeric.every(function (key) {
                var input = field(row, key);
                return !input || input.value.trim() === '';
            });
        }

        function announce(message) {
            if (!live) return;
            live.textContent = message;
        }

        function updateRowSummary(row) {
            var summary = row.querySelector('[data-row-summary]');
            if (!summary) return;
            var nameInput = field(row, 'name');
            var name = nameInput ? nameInput.value.trim() : '';
            var type = rowType(row);
            var sets = numericValue(row, 'sets');
            var reps = numericValue(row, 'reps');
            var weight = numericValue(row, 'weight_kg');
            var seconds = numericValue(row, 'seconds');
            var minutes = numericValue(row, 'minutes');
            var distance = numericValue(row, 'distance_km');
            var detail = '';
            if (type === 'timed') {
                if (sets && seconds) detail = sets + '×' + seconds + ' s';
                else if (seconds) detail = seconds + ' s';
                else if (sets) detail = sets + ' sets';
            } else if (type === 'cardio') {
                var parts = [];
                if (minutes) parts.push(minutes + ' min');
                if (distance !== null) parts.push(formatNumber(distance) + ' km');
                detail = parts.join(' · ');
            } else {
                if (sets && reps) detail = sets + '×' + reps;
                else if (reps) detail = reps + ' reps';
                else if (sets) detail = sets + ' sets';
                if (weight !== null) {
                    detail = detail ? detail + ' @ ' + formatNumber(weight) + ' kg' : '@ ' + formatNumber(weight) + ' kg';
                }
            }
            if (!name && !detail) {
                summary.textContent = 'New exercise';
                return;
            }
            summary.textContent = name && detail ? name + ' — ' + detail : (name || detail);
        }

        function updateTypeFields(row) {
            var type = rowType(row);
            Array.prototype.forEach.call(row.querySelectorAll('[data-type-fields]'), function (group) {
                var types = (group.getAttribute('data-type-fields') || '').split(/\s+/);
                group.hidden = types.indexOf(type) === -1;
            });
        }

        function syncRowAccessibility(row, index) {
            var name = field(row, 'name');
            var suggest = row.querySelector('[data-suggest]');
            if (name && suggest) {
                var suggestId = (name.id || ('exercise-name-' + index)) + '-suggest';
                suggest.id = suggestId;
                name.setAttribute('aria-controls', suggestId);
            }
            var order = field(row, 'order');
            if (order) order.value = String(index);
            var moveUp = row.querySelector('[data-move-up]');
            var moveDown = row.querySelector('[data-move-down]');
            if (moveUp) moveUp.disabled = index === 0;
            if (moveDown) moveDown.disabled = index === rowNodes().length - 1;
            Array.prototype.forEach.call(row.querySelectorAll('.errorlist'), function (errors) {
                var control = errors.parentElement
                    ? errors.parentElement.querySelector('input, select')
                    : null;
                if (!control) return;
                var errorId = control.id + '-errors';
                errors.id = errorId;
                control.setAttribute('aria-invalid', 'true');
                control.setAttribute('aria-describedby', errorId);
            });
            updateRowSummary(row);
        }

        function syncRow(row, index) {
            updateTypeFields(row);
            syncRowAccessibility(row, index);
        }

        function reindexRows() {
            var list = rowNodes();
            list.forEach(function (row, index) {
                Array.prototype.forEach.call(row.querySelectorAll('[name]'), function (input) {
                    input.name = input.name.replace(/^exercises-\d+-/, 'exercises-' + index + '-');
                });
                Array.prototype.forEach.call(row.querySelectorAll('[id]'), function (node) {
                    node.id = node.id.replace(/^id_exercises-\d+-/, 'id_exercises-' + index + '-');
                });
                Array.prototype.forEach.call(row.querySelectorAll('label[for]'), function (label) {
                    label.htmlFor = label.htmlFor.replace(/^id_exercises-\d+-/, 'id_exercises-' + index + '-');
                });
                syncRow(row, index);
            });
            total.value = String(list.length);
            if (initial) initial.value = '0';
            updateEstimate();
        }

        function estimateMinutes() {
            var minutes = 0;
            rowNodes().forEach(function (row) {
                if (isBlank(row)) return;
                var type = rowType(row);
                var sets = numericValue(row, 'sets');
                var seconds = numericValue(row, 'seconds');
                var cardioMinutes = numericValue(row, 'minutes');
                if (type === 'strength' && sets) {
                    minutes += sets * 3;
                } else if (type === 'timed') {
                    if (sets && seconds) minutes += (sets * seconds + sets * 30) / 60;
                    else if (seconds) minutes += seconds / 60;
                } else if (type === 'cardio' && cardioMinutes) {
                    minutes += cardioMinutes;
                }
            });
            if (!minutes) return null;
            return Math.max(1, Math.round(minutes / 5) * 5);
        }

        function updateDurationButton() {
            if (!useEstimate) return;
            var hasDuration = duration ? duration.value.trim() !== '' : true;
            useEstimate.disabled = !lastEstimate || hasDuration;
            useEstimate.setAttribute('aria-disabled', useEstimate.disabled ? 'true' : 'false');
        }

        function updateEstimate() {
            var minutes = estimateMinutes();
            lastEstimate = minutes;
            if (estimateWrap) estimateWrap.hidden = !minutes;
            if (estimateText) {
                estimateText.textContent = minutes ? 'Estimated ~' + minutes + ' min' : '';
            }
            updateDurationButton();
        }

        function updateToggle(row) {
            var button = row.querySelector('[data-toggle-fields]');
            if (!button) return;
            var editing = row.classList.contains('is-editing');
            button.textContent = editing ? 'Done' : 'Edit';
            button.setAttribute('aria-expanded', editing ? 'true' : 'false');
        }

        function fillRow(row, data) {
            ['name', 'type', 'sets', 'reps', 'weight_kg', 'seconds', 'minutes', 'distance_km'].forEach(function (key) {
                var input = field(row, key);
                if (!input || data[key] === undefined || data[key] === null) return;
                input.value = String(data[key]);
            });
        }

        function addRow(data) {
            if (rowNodes().length >= maxRows) {
                announce('You can add up to ' + maxRows + ' exercises.');
                return;
            }
            var index = rowNodes().length;
            var html = empty.innerHTML.replace(/__prefix__/g, String(index));
            rows.insertAdjacentHTML('beforeend', html);
            var row = rows.lastElementChild;
            if (data) fillRow(row, data);
            reindexRows();
            if (row) {
                var name = field(row, 'name');
                if (name) name.focus();
            }
            announce('Exercise added.');
        }

        function removeRow(row) {
            row.remove();
            reindexRows();
            addButton.focus();
            announce('Exercise removed.');
        }

        function moveRow(row, delta) {
            var list = rowNodes();
            var index = list.indexOf(row);
            var target = index + delta;
            if (index < 0 || target < 0 || target >= list.length) return;
            if (delta < 0) {
                rows.insertBefore(row, list[target]);
            } else {
                rows.insertBefore(list[target], row);
            }
            reindexRows();
            var handle = row.querySelector('[data-drag-handle]');
            if (handle) handle.focus();
            var name = field(row, 'name');
            announce('Moved ' + (name && name.value.trim() ? name.value.trim() : 'exercise') + '.');
        }

        function closeSuggest() {
            if (!openState) return;
            var suggest = openState.row.querySelector('[data-suggest]');
            var name = field(openState.row, 'name');
            if (suggest) {
                suggest.hidden = true;
                suggest.replaceChildren();
            }
            if (name) {
                name.setAttribute('aria-expanded', 'false');
                name.removeAttribute('aria-activedescendant');
            }
            openState = null;
            activeIndex = -1;
        }

        function setActive(index) {
            if (!openState) return;
            var suggest = openState.row.querySelector('[data-suggest]');
            if (!suggest) return;
            var options = suggest.querySelectorAll('[data-option]');
            if (!options.length) return;
            activeIndex = (index + options.length) % options.length;
            Array.prototype.forEach.call(options, function (option, optionIndex) {
                var selected = optionIndex === activeIndex;
                option.classList.toggle('is-active', selected);
                option.setAttribute('aria-selected', selected ? 'true' : 'false');
            });
            var name = field(openState.row, 'name');
            if (name) name.setAttribute('aria-activedescendant', options[activeIndex].id);
        }

        function selectExercise(row, name, type) {
            var nameInput = field(row, 'name');
            var typeInput = field(row, 'type');
            if (nameInput) nameInput.value = name;
            if (typeInput && type) typeInput.value = type;
            updateTypeFields(row);
            updateRowSummary(row);
            updateEstimate();
            closeSuggest();
            if (nameInput) nameInput.focus();
        }

        function createExercise(row, name) {
            announce('Saving ' + name + '.');
            var token = form ? form.querySelector('[name="csrfmiddlewaretoken"]') : null;
            var headers = {'Content-Type': 'application/json'};
            if (token) headers['X-CSRFToken'] = token.value;
            fetch(createUrl, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({name: name, type: rowType(row)})
            }).then(function (response) {
                return response.json().catch(function () {
                    return {};
                }).then(function (body) {
                    return {ok: response.ok, body: body};
                });
            }).then(function (result) {
                if (!result.ok) {
                    var message = result.body.error || 'Could not create that exercise.';
                    announce(message);
                    return;
                }
                var exists = catalog.some(function (item) {
                    return item.name.toLowerCase() === result.body.name.toLowerCase();
                });
                if (!exists) catalog.push(result.body);
                selectExercise(row, result.body.name, result.body.type);
                announce(result.body.name + ' saved.');
            }).catch(function () {
                announce('Could not create that exercise.');
            });
        }

        function optionButton(label, meta, attributes) {
            var button = document.createElement('button');
            button.type = 'button';
            button.className = 'fl-exercise-option';
            button.setAttribute('role', 'option');
            button.setAttribute('data-option', 'true');
            button.setAttribute('aria-selected', 'false');
            Object.keys(attributes || {}).forEach(function (key) {
                button.setAttribute(key, attributes[key]);
            });
            var name = document.createElement('span');
            name.className = 'fl-exercise-option-name';
            name.textContent = label;
            button.appendChild(name);
            if (meta) {
                var metaNode = document.createElement('span');
                metaNode.className = 'fl-exercise-option-meta';
                metaNode.textContent = meta;
                button.appendChild(metaNode);
            }
            return button;
        }

        function openSuggest(row) {
            var nameInput = field(row, 'name');
            var suggest = row.querySelector('[data-suggest]');
            if (!nameInput || !suggest) return;
            var query = nameInput.value.trim();
            var needle = query.toLowerCase();
            if (!needle) {
                closeSuggest();
                return;
            }
            var matches = catalog.filter(function (item) {
                if (!item || !item.name) return false;
                return item.name.toLowerCase().indexOf(needle) !== -1
                    || (item.muscle_group || '').toLowerCase().indexOf(needle) !== -1;
            }).sort(function (left, right) {
                var leftName = left.name.toLowerCase();
                var rightName = right.name.toLowerCase();
                var leftScore = leftName.indexOf(needle) === 0 ? 0 : 1;
                var rightScore = rightName.indexOf(needle) === 0 ? 0 : 1;
                return leftScore - rightScore || leftName.length - rightName.length;
            }).slice(0, 8);
            var exact = catalog.some(function (item) {
                return item && item.name && item.name.toLowerCase() === needle;
            });
            closeSuggest();
            openState = {row: row, matches: matches, query: query};
            suggest.replaceChildren();
            matches.forEach(function (item, index) {
                var button = optionButton(item.name, item.muscle_group || item.type, {
                    'data-option-index': String(index),
                    id: suggest.id + '-option-' + index
                });
                suggest.appendChild(button);
            });
            if (!exact) {
                suggest.appendChild(optionButton('Create "' + query + '"', 'Custom exercise', {
                    'data-create': 'true',
                    id: suggest.id + '-option-' + matches.length
                }));
            }
            suggest.hidden = false;
            nameInput.setAttribute('aria-expanded', 'true');
            setActive(0);
        }

        function chooseOption(row) {
            if (!openState || activeIndex < 0) return;
            var suggest = row.querySelector('[data-suggest]');
            if (!suggest) return;
            var options = suggest.querySelectorAll('[data-option]');
            var option = options[activeIndex];
            if (!option) return;
            if (option.getAttribute('data-create') === 'true') {
                createExercise(row, openState.query);
                return;
            }
            var match = openState.matches[Number(option.getAttribute('data-option-index'))];
            if (match) selectExercise(row, match.name, match.type);
        }

        function buildChips() {
            if (!chips || !chipList) return;
            chipList.replaceChildren();
            recent.slice(0, 5).forEach(function (item) {
                if (!item || !item.name) return;
                var button = document.createElement('button');
                button.type = 'button';
                button.className = 'fl-pill fl-exercise-chip';
                button.textContent = item.name;
                button.setAttribute('aria-label', 'Add ' + item.name);
                button.addEventListener('click', function () {
                    addRow(item);
                });
                chipList.appendChild(button);
            });
            chips.hidden = chipList.children.length === 0;
        }

        rows.addEventListener('click', function (event) {
            var button = event.target.closest('button');
            if (!button) return;
            var row = button.closest('[data-exercise-row]');
            if (!row) return;
            if (button.hasAttribute('data-remove-exercise')) {
                removeRow(row);
            } else if (button.hasAttribute('data-move-up')) {
                moveRow(row, -1);
            } else if (button.hasAttribute('data-move-down')) {
                moveRow(row, 1);
            } else if (button.hasAttribute('data-toggle-fields')) {
                row.classList.toggle('is-editing');
                updateToggle(row);
            }
        });

        rows.addEventListener('change', function (event) {
            if (!event.target.matches('[data-field="type"]')) return;
            var row = event.target.closest('[data-exercise-row]');
            updateTypeFields(row);
            updateRowSummary(row);
            updateEstimate();
        });

        rows.addEventListener('input', function (event) {
            var row = event.target.closest('[data-exercise-row]');
            if (!row) return;
            updateRowSummary(row);
            updateEstimate();
            if (event.target.matches('[data-field="name"]')) openSuggest(row);
        });

        rows.addEventListener('focusin', function (event) {
            if (!event.target.matches('[data-field="name"]')) return;
            openSuggest(event.target.closest('[data-exercise-row]'));
        });

        rows.addEventListener('keydown', function (event) {
            if (!event.target.matches('[data-field="name"]')) return;
            var row = event.target.closest('[data-exercise-row]');
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                if (!openState || openState.row !== row) openSuggest(row);
                if (!openState) return;
                event.preventDefault();
                setActive(activeIndex + (event.key === 'ArrowDown' ? 1 : -1));
            } else if (event.key === 'Enter') {
                if (openState && openState.row === row && activeIndex >= 0) {
                    event.preventDefault();
                    chooseOption(row);
                }
            } else if (event.key === 'Escape') {
                closeSuggest();
            } else if (event.key === 'Tab') {
                closeSuggest();
            }
        });

        rows.addEventListener('mousedown', function (event) {
            var option = event.target.closest('[data-option]');
            if (!option) return;
            event.preventDefault();
            if (!openState) return;
            var row = openState.row;
            activeIndex = Array.prototype.indexOf.call(
                row.querySelector('[data-suggest]').querySelectorAll('[data-option]'),
                option
            );
            chooseOption(row);
        });

        rows.addEventListener('dragstart', function (event) {
            var handle = event.target.closest('[data-drag-handle]');
            if (!handle) return;
            dragRow = handle.closest('[data-exercise-row]');
            if (!dragRow) return;
            dragRow.classList.add('is-dragging');
            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('text/plain', '');
        });

        rows.addEventListener('dragover', function (event) {
            if (!dragRow) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = 'move';
            var target = event.target.closest('[data-exercise-row]');
            if (!target || target === dragRow) return;
            var rect = target.getBoundingClientRect();
            var after = event.clientY > rect.top + rect.height / 2;
            rows.insertBefore(dragRow, after ? target.nextSibling : target);
        });

        rows.addEventListener('dragend', function () {
            if (!dragRow) return;
            dragRow.classList.remove('is-dragging');
            dragRow = null;
            reindexRows();
            announce('Exercise order updated.');
        });

        rows.addEventListener('drop', function (event) {
            event.preventDefault();
        });

        document.addEventListener('click', function (event) {
            if (!builder.contains(event.target)) closeSuggest();
        });

        if (addButton) {
            addButton.addEventListener('click', function () {
                addRow(null);
            });
        }

        if (useEstimate) {
            useEstimate.addEventListener('click', function () {
                if (!duration || !lastEstimate) return;
                if (duration.value.trim() !== '') return;
                duration.value = String(lastEstimate);
                duration.dispatchEvent(new Event('input', {bubbles: true}));
                updateDurationButton();
                announce('Estimated duration applied.');
            });
        }

        if (duration) {
            duration.addEventListener('input', updateDurationButton);
        }

        if (form) {
            form.addEventListener('submit', function () {
                reindexRows();
            });
        }

        var details = form ? form.querySelector('[data-more-details]') : null;
        if (details) {
            var mobileQuery = window.matchMedia('(max-width: 720px)');
            var syncDetails = function () {
                if (mobileQuery.matches) {
                    details.removeAttribute('open');
                } else {
                    details.setAttribute('open', '');
                }
            };
            syncDetails();
            if (mobileQuery.addEventListener) {
                mobileQuery.addEventListener('change', syncDetails);
            }
        }

        buildChips();
        rowNodes().forEach(function (row) {
            if (row.querySelector('.errorlist')) {
                row.classList.add('is-editing');
            }
            updateToggle(row);
        });
        reindexRows();
    }

    function start() {
        Array.prototype.forEach.call(
            document.querySelectorAll('[data-exercise-builder]'),
            init
        );
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();
