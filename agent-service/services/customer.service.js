/**
 * Builds customer context from pre-fetched data.
 * @param {Object} params
 * @param {Object|null} params.customer
 * @param {Object|null} params.lastOrder
 * @returns {Object}
 */
export function buildCustomerContext({ customer, lastOrder }) {
    const isReturning = !!customer;
    const customerName = customer ? customer.name : null;
    
    let lastOrderSummary = null;
    let suggestReorder = false;
    
    if (lastOrder) {
        lastOrderSummary = `${lastOrder.quantity} ${lastOrder.items}`; // items is typically the item name based on the prompt's slot structure
        
        const thirtyDaysAgo = Date.now() - (30 * 24 * 60 * 60 * 1000);
        const orderDate = new Date(lastOrder.createdAt).getTime();
        if (orderDate >= thirtyDaysAgo) {
            suggestReorder = true;
        }
    }
    
    return {
        isReturning,
        customerName,
        lastOrderSummary,
        suggestReorder
    };
}

/**
 * Parses the user message for a reorder intent affirmation.
 * @param {string} userMessage
 * @returns {boolean}
 */
export function parseReorderIntent(userMessage) {
    if (!userMessage) return false;
    
    const text = userMessage.toLowerCase();
    const keywords = ['yes', 'yeah', 'sure', 'ok', 'haan', 'bilkul', 'ho', 'hauda', 'haan ji'];
    
    return keywords.some(keyword => text.includes(keyword));
}

/**
 * Builds reorder slots based on the last order.
 * @param {Object} lastOrder
 * @returns {Object}
 */
export function buildReorderSlots(lastOrder) {
    if (!lastOrder) {
        return { item: null, quantity: null, address: null, deliveryDate: null, confirmed: false };
    }
    return {
        item: lastOrder.items || null,
        quantity: lastOrder.quantity || null,
        address: lastOrder.deliveryAddress || null,
        deliveryDate: lastOrder.deliveryDate || null,
        confirmed: false
    };
}
