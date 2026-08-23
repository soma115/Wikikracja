document.addEventListener('DOMContentLoaded', function() {
    const STORAGE_KEY = 'assets_table_columns';
    const DEFAULT_COLUMNS = ['uid', 'city', 'responsibilities', 'voivodeship'];

    // Field names in the same order as defined in UzytkownikTable.Meta.fields
    const FIELD_NAMES = ['uid', 'city', 'voivodeship', 'responsibilities', 'skills_knowledge_hobby', 'to_give_away', 'to_borrow', 'for_sale', 'i_need', 'want_to_learn', 'business', 'job', 'why'];
    
    const table = document.querySelector('table[data-column-toggle="true"]');
    if (!table) return;
    
    const headers = table.querySelectorAll('thead th');
    const columnLabels = {};
    const columnIndexToFieldName = {};
    
    // Map column index to field name and get label from header text
    headers.forEach((th, index) => {
        // Skip checkbox column if it exists (usually first column)
        if (th.querySelector('input[type="checkbox"]')) {
            return;
        }
        
        // Map index to field name (accounting for skipped columns)
        const fieldIndex = Object.keys(columnIndexToFieldName).length;
        if (fieldIndex < FIELD_NAMES.length) {
            const fieldName = FIELD_NAMES[fieldIndex];
            columnIndexToFieldName[index] = fieldName;
            columnLabels[fieldName] = th.textContent.trim();
        }
    });
    
    // Load saved columns from localStorage
    function getSavedColumns() {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                // Filter out any columns that don't exist in FIELD_NAMES
                return parsed.filter(col => FIELD_NAMES.includes(col));
            } catch (e) {
                return DEFAULT_COLUMNS;
            }
        }
        return DEFAULT_COLUMNS;
    }
    
    // Save columns to localStorage
    function saveColumns(columns) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(columns));
    }
    
    // Create column checkboxes
    const checkboxContainer = document.getElementById('column-checkboxes');
    if (checkboxContainer) {
        const savedColumns = getSavedColumns();
        
        FIELD_NAMES.forEach(fieldName => {
            const wrapper = document.createElement('div');
            wrapper.className = 'form-check';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'form-check-input';
            checkbox.id = `col-${fieldName}`;
            checkbox.value = fieldName;
            checkbox.checked = savedColumns.includes(fieldName);
            
            const label = document.createElement('label');
            label.className = 'form-check-label';
            label.htmlFor = `col-${fieldName}`;
            label.textContent = columnLabels[fieldName] || fieldName;
            
            checkbox.addEventListener('change', function() {
                const checked = Array.from(checkboxContainer.querySelectorAll('input:checked')).map(cb => cb.value);
                saveColumns(checked);
                toggleColumns(checked);
            });
            
            wrapper.appendChild(checkbox);
            wrapper.appendChild(label);
            checkboxContainer.appendChild(wrapper);
        });
        
        // Initial column toggle
        toggleColumns(savedColumns);
    }
    
    // Toggle column visibility
    function toggleColumns(visibleColumns) {
        const rows = table.querySelectorAll('tbody tr');
        const headerCells = table.querySelectorAll('thead th');
        
        headerCells.forEach((th, index) => {
            const fieldName = columnIndexToFieldName[index];
            if (fieldName) {
                th.style.display = visibleColumns.includes(fieldName) ? '' : 'none';
            }
        });
        
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            cells.forEach((td, index) => {
                const fieldName = columnIndexToFieldName[index];
                if (fieldName) {
                    td.style.display = visibleColumns.includes(fieldName) ? '' : 'none';
                }
            });
        });
    }
    
    // Global search functionality
    const searchInput = document.getElementById('global-search');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const rows = table.querySelectorAll('tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    }
});
