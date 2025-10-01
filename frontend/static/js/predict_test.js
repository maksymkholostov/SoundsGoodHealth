/**
 * predict_test.js
 * Simple test script to debug dictionary loading issues
 */

// Function to test dictionary loading
function testDictionaryLoading() {
    console.log('TESTING: Starting dictionary API test...');
    console.log('TESTING: Current User ID:', currentUserId);
    
    // Try to fetch dictionaries directly with fetch API
    fetch('/api/dictionary/list?scope=user')
        .then(response => {
            console.log('TESTING: Dictionary API response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('TESTING: Dictionary API response data:', data);
            if (data.success && data.dictionaries) {
                console.log('TESTING: Found dictionaries:', data.dictionaries.length);
                data.dictionaries.forEach(dict => {
                    console.log('TESTING: Dictionary:', dict.name, dict.id);
                });
            } else {
                console.log('TESTING: No dictionaries found in response');
            }
        })
        .catch(error => {
            console.error('TESTING: Error loading dictionaries:', error);
        });
}

// Run the test when the page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('TESTING: DOM loaded, running test in 2 seconds...');
    setTimeout(testDictionaryLoading, 2000); // Delay to ensure other scripts have loaded
}); 