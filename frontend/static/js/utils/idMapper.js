(function() { // Start IIFE
  console.log("--- idMapper.js script started ---");
  /**
   * ID Mapper Utility
   * Fetches and provides human-readable names for IDs throughout the application
   */

  // Cache for ID-to-name mappings
  let mappingCache = null; // Restore original declaration inside IIFE
  let loadPromise = null;
  let retryCount = 0;
  const MAX_RETRIES = 3;
  const RETRY_DELAY = 1000; // milliseconds

  // Create a default empty mapping structure to use as fallback
  const DEFAULT_MAPPINGS = {
    'class_id': {},
    'model_id': {},
    'sound_id': {},
    'feature_id': {},
    'dictionary_id': {}
  };

  // Initialize mappings with empty defaults
  mappingCache = {...DEFAULT_MAPPINGS};

  // Load all ID mappings from the server
  function loadMappings() {
    console.log("--- idMapper.js: loadMappings() called ---");
    // If we already have a cache, return it immediately
    // Check specifically for class_id as an indicator of loaded data, not just empty structure
    if (mappingCache && mappingCache.class_id && Object.keys(mappingCache.class_id).length > 0) {
         console.log('ID Mapper: Using cached mappings.');
        return Promise.resolve(mappingCache);
    }
    
    // If we're already loading, return that promise
    if (loadPromise) {
        console.log('ID Mapper: Load already in progress, returning existing promise.');
        return loadPromise;
    }
    
    console.log('ID Mapper: Loading mappings from server...');
    
    loadPromise = fetchWithRetry('/api/id-mappings');
    
    // Add a finally block to reset loadPromise when done (success or fail)
    loadPromise.finally(() => {
        loadPromise = null; 
    });

    return loadPromise;
  }

  // Fetch with retry logic for better error handling
  function fetchWithRetry(url, attempt = 0) {
    console.log(`--- idMapper.js: fetchWithRetry called for URL: ${url}, attempt: ${attempt} ---`);
    return fetch(url)
      .then(response => {
        if (!response.ok) {
          const statusCode = response.status;
          
          // Log the error
          console.warn(`ID Mapper: Received ${statusCode} from ${url}`);
          
          // For server errors (5xx), retry if we haven't exceeded max retries
          if (statusCode >= 500 && attempt < MAX_RETRIES) {
            console.info(`ID Mapper: Retrying (${attempt + 1}/${MAX_RETRIES}) after ${RETRY_DELAY}ms`);
            
            return new Promise(resolve => {
              setTimeout(() => {
                resolve(fetchWithRetry(url, attempt + 1));
              }, RETRY_DELAY * (attempt + 1)); // Increasing delay for each retry
            });
          }
          
          throw new Error(`Failed to load ID mappings (${statusCode})`);
        }
        return response.json();
      })
      .then(data => {
        // Success! Store the mappings in cache
        console.log("ID Mapper: Received data from /api/id-mappings:", JSON.stringify(data));
        mappingCache = {...DEFAULT_MAPPINGS, ...data};
        console.log('ID Mapper: Loaded mappings successfully');
        return mappingCache;
      })
      .catch(error => {
        console.error('ID Mapper: Error loading mappings:', error);
        // loadPromise = null; // Moved to finally block
        
        // Fall back to empty mappings but don't block the application
        console.warn('ID Mapper: Using fallback empty mappings');
         // Ensure mappingCache is at least the default structure on error
         if (!mappingCache || Object.keys(mappingCache.class_id || {}).length === 0) {
             mappingCache = {...DEFAULT_MAPPINGS};
         }
        return mappingCache; // Return current cache (which might just be defaults)
      });
  }

  // Get a human-readable name for an ID - with synchronous fallback
  function getName(id, type) {
    if (!id) return '';
    
    // ADDED: Log the lookup attempt
    console.log(`>>> IdMapper.getName: Looking up ID '${id}' of type '${type}'`);

    if (!mappingCache || !mappingCache[type]) {
      console.warn(`ID Mapper: No mappings cache or type '${type}' found. Cache:`, mappingCache);
      if (!loadPromise) { loadMappings(); } 
      return id; // Return ID as fallback
    }
    
    const name = mappingCache[type][id];
    
    // ADDED: Log the result
    if (!name) {
       console.warn(`ID Mapper: Mapping NOT FOUND for type '${type}', ID '${id}'. Returning ID.`);
       // console.log(`>>> IdMapper.getName: Current keys for type '${type}':`, Object.keys(mappingCache[type])); // Optional: Very verbose
    } else {
        console.log(`>>> IdMapper.getName: Found name '${name}' for ID '${id}'`);
    }
    // --- END ADDED LOGS ---
    
    return name || id; // Return found name or ID fallback
  }

  // Convenience functions for specific ID types
  const IdMapper = {
    getClassName: (id) => getName(id, 'class_id'),
    getModelName: (id) => getName(id, 'model_id'),
    getSoundName: (id) => getName(id, 'sound_id'),
    getFeatureName: (id) => getName(id, 'feature_id'),
    getDictionaryName: (id) => getName(id, 'dictionary_id'),
    
    // --- ADDED: Get all mappings for a type --- 
    getAllClassMappings: () => { 
        return mappingCache && mappingCache.class_id ? {...mappingCache.class_id} : {}; // Return a copy 
    },
    // Could add similar helpers for other types if needed
    // --- END ADDED --- 

    // Initialize by loading mappings when script is loaded
    init: function() {
      console.log("--- idMapper.js: Calling IdMapper.init() --- ");
      if (!loadPromise) { // Only init if not already loading
           return loadMappings(); // RETURN the promise
       }
       return loadPromise; // Return existing promise if already loading
    },
    
    // Force reload of mappings (useful if data has changed)
    reload: function() {
      console.log('ID Mapper: Force reloading mappings');
      // loadPromise = null; // Resetting is handled by loadMappings now
      return loadMappings(); // Will create a new promise
    },
    
    // Debug method to check mapping status
    getDebugInfo: function() {
      const info = {
        isMappingCacheInitialized: !!mappingCache,
        hasClassMappings: mappingCache && mappingCache.class_id && Object.keys(mappingCache.class_id).length > 0,
        classIdCount: mappingCache && mappingCache.class_id ? Object.keys(mappingCache.class_id).length : 0,
        classIdSample: mappingCache && mappingCache.class_id ? Object.entries(mappingCache.class_id).slice(0, 3) : [],
        availableTypes: mappingCache ? Object.keys(mappingCache) : [],
        isLoading: !!loadPromise // Check if a load is currently in progress
      };
      return JSON.stringify(info, null, 2);
    }
  };

  // Initialize the mapper
  console.log("--- idMapper.js: Calling IdMapper.init() --- ");
  IdMapper.init();

  // Export for use in other files
  window.IdMapper = IdMapper;

})(); // End IIFE
