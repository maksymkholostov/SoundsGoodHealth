// CSRF Token handling for AJAX requests
function getCSRFToken() {
    const token = document.querySelector('meta[name="csrf-token"]');
    return token ? token.getAttribute('content') : null;
}

// Add CSRF token to fetch requests
function fetchWithCSRF(url, options = {}) {
    const token = getCSRFToken();
    if (token) {
        if (!options.headers) {
            options.headers = {};
        }
        options.headers['X-CSRFToken'] = token;
    }
    return fetch(url, options);
}

// Add CSRF token to FormData
function addCSRFTokenToFormData(formData) {
    const token = getCSRFToken();
    if (token) {
        formData.append('csrf_token', token);
    }
    return formData;
}

// Add CSRF token to JSON data
function addCSRFTokenToJSON(data) {
    const token = getCSRFToken();
    if (token) {
        data.csrf_token = token;
    }
    return data;
}
