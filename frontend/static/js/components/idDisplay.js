/**
 * ID Display Component
 * Displays human-readable names instead of IDs
 */
class IdDisplay {
  /**
   * Create an ID display element
   * @param {Object} options - Configuration options
   * @param {string} options.id - The ID to display
   * @param {string} options.type - The type of ID ('class_id', 'model_id', etc.)
   * @param {boolean} options.showTooltip - Whether to show the ID as a tooltip
   * @param {string} options.element - The element to update (optional)
   * @returns {HTMLElement} The created or updated element
   */
  static create(options) {
    // Ensure IdMapper is loaded
    if (!window.IdMapper) {
      console.error('IdMapper not loaded. Make sure to include idMapper.js before idDisplay.js');
      return document.createTextNode(options.id || '');
    }
    
    // Get the name for this ID
    const name = IdMapper[`get${options.type.split('_')[0].charAt(0).toUpperCase() + options.type.split('_')[0].slice(1)}Name`](options.id);
    
    // Create or use existing element
    const element = options.element || document.createElement('span');
    element.textContent = name;
    
    // Add tooltip if requested
    if (options.showTooltip && options.id) {
      element.title = options.id;
    }
    
    return element;
  }
  
  /**
   * Update all elements with data-id and data-type attributes
   * Call this after loading a page with ID elements
   */
  static updateAll() {
    document.querySelectorAll('[data-id][data-type]').forEach(el => {
      const id = el.dataset.id;
      const type = el.dataset.type;
      if (id && type) {
        IdDisplay.create({
          id: id,
          type: type,
          showTooltip: el.dataset.showTooltip !== 'false',
          element: el
        });
      }
    });
  }
}

// Export for use in other files
window.IdDisplay = IdDisplay;

// Update all ID displays when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  IdDisplay.updateAll();
});
