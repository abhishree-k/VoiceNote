import { initSlots } from './slots.service.js';

const sessions = new Map();

/**
 * Creates a new session.
 * @param {Object} params
 * @param {string} params.callSid
 * @param {string} params.callId
 * @param {string} params.customerId
 * @param {string} params.language
 * @returns {Object}
 */
export function createSession({ callSid, callId, customerId, language }) {
    const session = {
        callSid,
        callId,
        customerId,
        language,
        slots: initSlots(),
        products: [],
        history: [],
        failedAttempts: 0,
        confidenceScores: [],
        escalated: false,
        cancelled: false,
        reorderMode: false,
        createdAt: Date.now()
    };
    sessions.set(callSid, session);
    return session;
}

/**
 * Retrieves a session.
 * @param {string} callSid
 * @returns {Object|undefined}
 */
export function getSession(callSid) {
    return sessions.get(callSid);
}

/**
 * Updates a session.
 * @param {string} callSid
 * @param {Object} partialUpdate
 * @returns {Object|undefined}
 */
export function updateSession(callSid, partialUpdate) {
    const session = sessions.get(callSid);
    if (!session) return undefined;
    
    Object.assign(session, partialUpdate);
    return session;
}

/**
 * Adds a message to the session history (capped at 12).
 * @param {string} callSid
 * @param {string} role
 * @param {string} content
 */
export function addMessage(callSid, role, content) {
    const session = sessions.get(callSid);
    if (!session) return;
    
    session.history.push({ role, content });
    if (session.history.length > 12) {
        session.history = session.history.slice(session.history.length - 12);
    }
}

/**
 * Deletes a session.
 * @param {string} callSid
 */
export function deleteSession(callSid) {
    sessions.delete(callSid);
}

/**
 * Gets all sessions.
 * @returns {Map}
 */
export function getAllSessions() {
    return sessions;
}

/**
 * Gets the average confidence score for a session.
 * @param {string} callSid
 * @returns {number}
 */
export function getAverageConfidence(callSid) {
    const session = sessions.get(callSid);
    if (!session || session.confidenceScores.length === 0) return 1.0;
    
    const sum = session.confidenceScores.reduce((acc, val) => acc + val, 0);
    return sum / session.confidenceScores.length;
}
