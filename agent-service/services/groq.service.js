import 'dotenv/config';

/**
 * Calls the Groq API for chat completions.
 * @param {Object} params
 * @param {Array<{role: string, content: string}>} params.messages
 * @param {string} [params.model="llama-3.3-70b-versatile"]
 * @param {number} [params.temperature=0.3]
 * @param {boolean} [params.json=false]
 * @returns {Promise<string>}
 */
export async function callGroq({ messages, model = "llama-3.3-70b-versatile", temperature = 0.3, json = false }) {
    try {
        const payload = {
            model,
            messages,
            temperature,
        };

        if (json) {
            payload.response_format = { type: "json_object" };
        }

        const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${process.env.GROQ_API_KEY}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
        }

        const data = await response.json();
        return data.choices[0].message.content;
    } catch (error) {
        throw new Error("GROQ_FAILED: " + error.message);
    }
}

/**
 * Safely parses a JSON string, stripping markdown fences if present.
 * @param {string} text
 * @returns {Object|null}
 */
export function safeParseJSON(text) {
    if (!text) return null;
    
    // Strip markdown fences
    let cleanedText = text.replace(/^```json/i, '').replace(/```$/, '').trim();
    
    try {
        return JSON.parse(cleanedText);
    } catch (error) {
        return null;
    }
}
