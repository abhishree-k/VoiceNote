import { callGroq, safeParseJSON } from './services/groq.service.js';
import { getSystemPrompt } from './services/prompt.service.js';
import { extractAndMergeSlots, formatOrderForVoice, isReadyToConfirm } from './services/slots.service.js';
import { createSession, updateSession, getSession, addMessage, deleteSession } from './services/session.service.js';
import { buildCustomerContext, buildReorderSlots, parseReorderIntent } from './services/customer.service.js';
import { detectEscalationKeywords, shouldEscalate, getEscalationMessage } from './services/escalation.service.js';

/**
 * Starts a new call.
 * @param {Object} params
 * @param {string} params.callSid
 * @param {string} params.callId
 * @param {string} params.customerId
 * @param {Object} params.customerData
 * @param {string} params.language
 * @param {Array<{name: string, price: number, sku: string}>} params.products
 * @returns {Promise<Object>}
 */
export async function startCall({ callSid, callId, customerId, customerData, language, products }) {
    createSession({ callSid, callId, customerId, language });
    updateSession(callSid, { products, customerData, lastOrder: customerData?.lastOrder });
    
    const context = buildCustomerContext(customerData || { customer: null, lastOrder: null });
    
    if (context.suggestReorder) {
        updateSession(callSid, { reorderMode: "pending" });
    }
    
    const systemPrompt = getSystemPrompt({
        language,
        customerName: context.customerName,
        lastOrderSummary: context.lastOrderSummary,
        products
    });
    
    const messages = [
        { role: "system", content: systemPrompt },
        { role: "user", content: "start" }
    ];
    
    const groqReply = await callGroq({ messages });
    addMessage(callSid, "assistant", groqReply);
    
    return {
        type: "greeting",
        reply: groqReply,
        callSid,
        language,
        isReturningCustomer: context.isReturning,
        transcriptEntry: { role: "bot", message: groqReply }
    };
}

/**
 * Processes a turn in the conversation.
 * @param {Object} params
 * @param {string} params.callSid
 * @param {string} params.userMessage
 * @param {number} params.sttConfidence
 * @returns {Promise<Object>}
 */
export async function processCall({ callSid, userMessage, sttConfidence }) {
    const session = getSession(callSid);
    if (!session) {
        throw new Error("Session not found");
    }
    
    addMessage(callSid, "user", userMessage);
    session.confidenceScores.push(sttConfidence ?? 1.0);
    
    if ((sttConfidence ?? 1.0) < 0.45) {
        session.failedAttempts++;
    }
    
    const escalationCheck1 = detectEscalationKeywords(userMessage);
    if (escalationCheck1.escalate) {
        session.escalated = true;
    }
    
    const escalationCheck2 = shouldEscalate(session);
    if (escalationCheck2.escalate) {
        const msg = getEscalationMessage(session.language);
        return {
            type: "escalated",
            reply: msg,
            reason: escalationCheck2.reason,
            escalated: true,
            transcriptEntry: { role: "bot", message: msg }
        };
    }
    
    // Check reorder mode first
    // Note: We need customerData.lastOrder to build slots. However, in processCall we don't have customerData directly passed.
    // Wait, the prompt says: "if session.reorderMode === 'pending' and parseReorderIntent(userMessage): updateSession(callSid, { slots:buildReorderSlots(customerData.lastOrder), reorderMode:'confirmed' })"
    // So customerData.lastOrder needs to be either fetched or stored in session.
    // I should store customerData in the session during startCall so it's available here.
    // Let's assume the user meant to store it, so I'll retrieve it. 
    // Actually, I can just store `lastOrder` in the session in startCall. Let me fix the startCall implicitly by assuming it is in session, or I'll just check if session has it. 
    // Let's modify session.lastOrder. Wait, I'll just use it if available.
    if (session.reorderMode === "pending" && parseReorderIntent(userMessage)) {
        updateSession(callSid, { 
            slots: buildReorderSlots(session.lastOrder), 
            reorderMode: "confirmed" 
        });
    }
    
    const extraction = await extractAndMergeSlots({
        userMessage,
        currentSlots: session.slots,
        language: session.language,
        products: session.products
    });
    
    updateSession(callSid, { slots: extraction.updatedSlots });
    
    if (extraction.changedKeys.length === 0) {
        session.failedAttempts++;
    }
    
    // We need to re-generate the system prompt or just rely on the existing prompt in history?
    // The prompt says "messages = [systemPrompt, ...session.history]".
    // We need customerName, lastOrderSummary, products for systemPrompt. 
    // We can rebuild system prompt with session.customerData.
    const context = buildCustomerContext({ customer: session.customerData?.customer, lastOrder: session.lastOrder });
    const systemPrompt = getSystemPrompt({
        language: session.language,
        customerName: context.customerName,
        lastOrderSummary: context.lastOrderSummary,
        products: session.products
    });
    
    const messages = [
        { role: "system", content: systemPrompt },
        ...session.history
    ];
    
    const groqReply = await callGroq({ messages });
    addMessage(callSid, "assistant", groqReply);
    
    const parsed = safeParseJSON(groqReply);
    if (parsed) {
        if (parsed.status === "confirmed") {
            const unitPrice = session.products.find(p => p.name.toLowerCase() === session.slots.item?.toLowerCase())?.price || 0;
            const readback = formatOrderForVoice(session.slots, session.language, unitPrice);
            return {
                type: "confirmed",
                reply: readback,
                slots: { ...session.slots, confirmed: true },
                orderPayload: {
                    item: session.slots.item,
                    quantity: session.slots.quantity,
                    unitPrice,
                    address: session.slots.address,
                    deliveryDate: session.slots.deliveryDate,
                    language: session.language
                },
                escalated: false,
                transcriptEntry: { role: "bot", message: readback }
            };
        }
        
        if (parsed.status === "cancelled") {
            const replyMsg = "Your order has been cancelled. Thank you for calling.";
            return {
                type: "cancelled",
                reply: replyMsg,
                escalated: false,
                transcriptEntry: { role: "bot", message: replyMsg }
            };
        }
        
        if (parsed.status === "escalated") {
            const reason = ["low_confidence", "customer_request", "error"].includes(parsed.reason) ? parsed.reason : "error";
            const msg = getEscalationMessage(session.language);
            return {
                type: "escalated",
                reply: msg,
                reason,
                escalated: true,
                transcriptEntry: { role: "bot", message: msg }
            };
        }
    }
    
    // Normal turn
    const keys = ["item", "quantity", "address", "deliveryDate"];
    const missingSlots = keys.filter(k => session.slots[k] === null || session.slots[k] === undefined);
    
    return {
        type: "turn",
        reply: groqReply,
        slots: session.slots,
        missingSlots,
        escalated: false,
        confidence: extraction.confidence,
        transcriptEntry: { role: "bot", message: groqReply }
    };
}

/**
 * Ends a call.
 * @param {Object} params
 * @param {string} params.callSid
 * @returns {Promise<Object>}
 */
export async function endCall({ callSid }) {
    const session = getSession(callSid);
    if (!session) {
        throw new Error("Session not found");
    }
    
    const summary = { ...session };
    deleteSession(callSid);
    
    return {
        callSid,
        callId: summary.callId,
        duration: Date.now() - summary.createdAt,
        finalSlots: summary.slots,
        wasConfirmed: summary.slots.confirmed,
        wasEscalated: summary.escalated,
        wasCancelled: summary.cancelled,
        turnCount: Math.floor(summary.history.length / 2)
    };
}
