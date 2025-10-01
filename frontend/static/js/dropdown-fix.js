// dropdown-fix.js - A simple script to ensure dropdowns work properly
document.addEventListener('DOMContentLoaded', function() {
    // Wait for the document to fully load
    setTimeout(function() {
        console.log('Running dropdown-fix.js');
        
        // Fix dropdown visibility
        fixDropdownVisibility();
        
        // Add event listeners for radio buttons
        setupRadioButtonListeners();
        
        // Check for special query parameter that forces class selection
        checkForForceSelection();
    }, 300);
    
    function fixDropdownVisibility() {
        // Find the dropdown by ID
        var dropdown = document.getElementById('allClassesSelect');
        if (!dropdown) {
            console.error('dropdown-fix.js: Could not find allClassesSelect dropdown');
            return;
        }
        
        // Fix the style to ensure it's visible
        dropdown.style.display = 'block';
        dropdown.style.opacity = '1';
        dropdown.style.visibility = 'visible';
        dropdown.style.position = 'static';
        dropdown.style.width = '100%';
        dropdown.style.height = 'auto';
        
        // Log the options to console
        console.log('Dropdown found with ' + dropdown.options.length + ' options');
        for (var i = 0; i < dropdown.options.length; i++) {
            console.log('Option ' + i + ': ' + dropdown.options[i].value);
        }
        
        // If there's only one element (the empty option), we might need to force refresh
        if (dropdown.options.length <= 1) {
            console.warn('Only found the empty option, something might be wrong');
        }
    }
    
    function setupRadioButtonListeners() {
        // Get radio buttons
        var allClassesOption = document.getElementById('allClassesOption');
        var newClassOption = document.getElementById('newClassOption');
        
        // Get sections
        var allClassesSection = document.getElementById('allClassesSection');
        var newClassSection = document.getElementById('newClassSection');
        
        if (allClassesOption && newClassOption) {
            // Add click listeners (not change, to ensure they fire)
            allClassesOption.addEventListener('click', function() {
                if (allClassesSection) allClassesSection.style.display = 'block';
                if (newClassSection) newClassSection.style.display = 'none';
            });
            
            newClassOption.addEventListener('click', function() {
                if (allClassesSection) allClassesSection.style.display = 'none';
                if (newClassSection) newClassSection.style.display = 'block';
            });
        }
    }
    
    function checkForForceSelection() {
        // Check URL for force parameter
        var urlParams = new URLSearchParams(window.location.search);
        var forceClass = urlParams.get('force_class');
        
        if (forceClass) {
            var dropdown = document.getElementById('allClassesSelect');
            if (dropdown) {
                // Try to find and select this class
                for (var i = 0; i < dropdown.options.length; i++) {
                    if (dropdown.options[i].value === forceClass) {
                        dropdown.selectedIndex = i;
                        
                        // Trigger change event
                        var event = new Event('change');
                        dropdown.dispatchEvent(event);
                        
                        console.log('Force-selected class: ' + forceClass);
                        break;
                    }
                }
            }
        }
    }
}); 