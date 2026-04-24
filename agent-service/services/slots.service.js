import { callGroq, safeParseJSON } from './groq.service.js';
import { getSlotExtractionPrompt } from './prompt.service.js';

/**
 * Initializes empty slots.
 * @returns {Object}
 */
export function initSlots() {
    return { item: null, quantity: null, address: null, deliveryDate: null, confirmed: false };
}

/**
 * Extracts and merges slots from user message.
 * @param {Object} params
 * @param {string} params.userMessage
 * @param {Object} params.currentSlots
 * @param {string} params.language
 * @param {Array<{name: string, price: number, sku: string}>} params.products
 * @returns {Promise<{updatedSlots: Object, confidence: number, changedKeys: string[], correctionDetected: boolean}>}
 */
export async function extractAndMergeSlots({ userMessage, currentSlots, language, products }) {
    const messages = getSlotExtractionPrompt({ userMessage, currentSlots, language, products });
    
    let extractionText;
    try {
        extractionText = await callGroq({ messages, json: true, temperature: 0.1 });
    } catch (e) {
        return { updatedSlots: { ...currentSlots }, confidence: 0, changedKeys: [], correctionDetected: false };
    }

    const extraction = safeParseJSON(extractionText) || {};
    
    const updatedSlots = { ...currentSlots };
    const changedKeys = [];
    
    const checkKeys = ["item", "quantity", "address", "deliveryDate"];
    
    for (const key of checkKeys) {
        if (extraction[key] !== undefined && extraction[key] !== null) {
            if (updatedSlots[key] !== extraction[key]) {
                updatedSlots[key] = extraction[key];
                changedKeys.push(key);
            }
        }
    }
    
    return {
        updatedSlots,
        confidence: extraction.confidence ?? 1.0,
        changedKeys,
        correctionDetected: extraction.correctionDetected ?? false
    };
}

/**
 * Gets missing slots excluding 'confirmed'.
 * @param {Object} slots
 * @returns {string[]}
 */
export function getMissingSlots(slots) {
    const keys = ["item", "quantity", "address", "deliveryDate"];
    return keys.filter(k => slots[k] === null || slots[k] === undefined);
}

/**
 * Checks if all required slots are filled.
 * @param {Object} slots
 * @returns {boolean}
 */
export function isReadyToConfirm(slots) {
    return getMissingSlots(slots).length === 0;
}

/**
 * Formats the order for voice readback.
 * @param {Object} slots
 * @param {string} language
 * @param {number} unitPrice
 * @returns {string}
 */
export function formatOrderForVoice(slots, language, unitPrice) {
    const { quantity, item, address, deliveryDate } = slots;
    
    // English: "You'd like [quantity] [item] at ₹[unitPrice each], delivered to [address] on [deliveryDate]. Shall I confirm?"
    // Hindi: "Aapko [quantity] [item] chahiye, jiska daam ₹[unitPrice each] hai, aur ye [address] par [deliveryDate] ko pahunchaya jayega. Kya main confirm karun?"
    // Kannada: "Nimage [quantity] [item] beku, idara bele ₹[unitPrice each], idannu [address] ge [deliveryDate] andu talupisalaguttade. Naanu confirm maadala?"
    // Marathi: "Tumhala [quantity] [item] pahije, jyachi kimmat ₹[unitPrice each] aahe, aani he [address] var [deliveryDate] la pohchavle jail. Mee confirm karu ka?"
    
    switch (language.toLowerCase()) {
        case "hindi":
            return `Aapko ${quantity} ${item} chahiye, jiska daam ₹${unitPrice} pratik hai, aur ye ${address} par ${deliveryDate} ko pahunchaya jayega. Kya main confirm karun?`;
        case "kannada":
            return `Nimage ${quantity} ${item} beku, idara bele ondkke ₹${unitPrice}, idannu ${address} ge ${deliveryDate} andu talupisalaguttade. Naanu confirm maadala?`;
        case "marathi":
            return `Tumhala ${quantity} ${item} pahije, jyachi kimmat ₹${unitPrice} pratyeki aahe, aani he ${address} var ${deliveryDate} la pohchavle jail. Mee confirm karu ka?`;
        case "english":
        default:
            return `You'd like ${quantity} ${item} at ₹${unitPrice} each, delivered to ${address} on ${deliveryDate}. Shall I confirm?`;
    }
}
