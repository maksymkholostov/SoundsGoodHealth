/**
 * dropdown_test.js
 * Direct test for dictionary dropdown functionality
 */

// Execute when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DROPDOWN TEST: Script loaded but test disabled (uncomment to test again)');
    
    // Delay to allow other scripts to load
    // setTimeout(testDropdown, 3000); // DISABLED - uncomment to run test again
});

// Test function to directly populate the dropdown
function testDropdown() {
    console.log('DROPDOWN TEST: Running dropdown test...');
    
    // Get the dropdown element
    const select = document.getElementById('dictionarySelect');
    if (!select) {
        console.error('DROPDOWN TEST: Could not find dictionarySelect element');
        return;
    }
    
    console.log('DROPDOWN TEST: Found select element:', select);
    
    // Create test data
    const testDictionaries = [
        { id: 'test1', name: 'Test Dictionary 1', displayName: 'Test Dictionary 1' },
        { id: 'test2', name: 'Test Dictionary 2', displayName: 'Test Dictionary 2' }
    ];
    
    // Clear existing options
    console.log('DROPDOWN TEST: Current options count:', select.options.length);
    select.innerHTML = '';
    console.log('DROPDOWN TEST: Cleared options, now count:', select.options.length);
    
    // Add default option
    const defaultOption = document.createElement('option');
    defaultOption.textContent = "-- Select a Test Dictionary --";
    defaultOption.value = "";
    defaultOption.selected = true;
    defaultOption.disabled = true;
    select.appendChild(defaultOption);
    console.log('DROPDOWN TEST: Added default option');
    
    // Add test options
    testDictionaries.forEach(dict => {
        const option = document.createElement('option');
        option.value = dict.id;
        option.textContent = dict.displayName;
        select.appendChild(option);
        console.log('DROPDOWN TEST: Added option:', dict.displayName);
    });
    
    console.log('DROPDOWN TEST: Final options count:', select.options.length);
    
    // Force the select to be visible
    select.style.display = 'block';
    select.style.visibility = 'visible';
    select.style.opacity = '1';
    select.style.maxWidth = '400px';
    select.style.border = '2px solid red'; // Highlight for debugging
    
    console.log('DROPDOWN TEST: Set select visibility styles');
    
    // Try to manually select the first real option
    try {
        select.selectedIndex = 1; // First non-default option
        console.log('DROPDOWN TEST: Manually selected index 1');
        
        // Dispatch a change event
        const event = new Event('change');
        select.dispatchEvent(event);
        console.log('DROPDOWN TEST: Dispatched change event');
    } catch (error) {
        console.error('DROPDOWN TEST: Error setting selection:', error);
    }
} 