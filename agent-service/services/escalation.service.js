import { getAverageConfidence } from './session.service.js';

const keywordsByLang = {
    english: ['agent', 'human', 'representative', 'operator', 'transfer', 'connect me'],
    hindi: ['agent', 'insaan', 'manav', 'madad karo', 'insaan se baat'],
    kannada: ['agent', 'manushya', 'sahaya', 'nimage agent beka'],
    marathi: ['agent', 'manoos', 'madad kara']
};

/**
 * Detects escalation keywords in a message.
 * @param {string} message
 * @returns {{escalate: boolean, keyword: string|null}}
 */
export function detectEscalationKeywords(message) {
    if (!message) return { escalate: false, keyword: null };
    
    const lowerMsg = message.toLowerCase();
    
    for (const [lang, keywords] of Object.entries(keywordsByLang)) {
        for (const keyword of keywords) {
            if (lowerMsg.includes(keyword)) {
                return { escalate: true, keyword };
            }
        }
    }
    
    return { escalate: false, keyword: null };
}

/**
 * Determines if the session should be escalated and the reason.
 * @param {Object} session
 * @returns {{escalate: boolean, reason: string|null}}
 */
export function shouldEscalate(session) {
    if (session.escalated) {
        return { escalate: true, reason: "customer_request" };
    }
    
    if (getAverageConfidence(session.callSid) < 0.45) {
        return { escalate: true, reason: "low_confidence" };
    }
    
    if (session.failedAttempts >= 3) {
        return { escalate: true, reason: "error" };
    }
    
    return { escalate: false, reason: null };
}

/**
 * Gets the escalation message in the correct language.
 * @param {string} language
 * @returns {string}
 */
export function getEscalationMessage(language) {
    switch (language.toLowerCase()) {
        case 'hindi':
            return "Main aapko hamare support team se connect kar raha hoon. Thoda rukiye.";
        case 'kannada':
            return "Naanu nimage support team annu connect maaduttiddene. Dayavittu nidhari.";
        case 'marathi':
            return "Mee tumhala support teamshi connect kartat. Ek kshan thamba.";
        case 'english':
        default:
            return "I'm connecting you to our support team now. Please hold.";
    }
}
