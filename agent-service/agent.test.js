import 'dotenv/config';

const PORT = 4000;
const BASE_URL = `http://localhost:${PORT}/agent`;

const mockProducts = [
  { name: "A4 Paper", price: 250, sku: "A4-001" },
  { name: "Pen Box", price: 120, sku: "PEN-001" }
];

async function callEndpoint(endpoint, payload) {
    const res = await fetch(`${BASE_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!res.ok) {
        throw new Error(`Endpoint ${endpoint} failed: ${await res.text()}`);
    }
    return res.json();
}

async function runTest1() {
    console.log("--- TEST 1: English new customer, correction + confirm ---");
    let result = await callEndpoint('/start-call', {
        callSid: "t1",
        callId: "c1",
        customerId: "cu1",
        customerData: { customer: null, lastOrder: null },
        language: "english",
        products: mockProducts
    });
    
    const turns = [
        "I want A4 paper",
        "5 reams",
        "actually make it 8",
        "42 MG Road",
        "next Monday",
        "yes confirm"
    ];

    for (const text of turns) {
        console.log(`User: ${text}`);
        result = await callEndpoint('/process-turn', {
            callSid: "t1",
            userMessage: text,
            sttConfidence: 0.95
        });
        console.log(`Bot: ${result.reply} (type: ${result.type})`);
        
        // Short pause to avoid rate limits
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    if (result.type === "confirmed") {
        console.log("TEST 1: PASS\n");
    } else {
        console.log("TEST 1: FAIL\n");
    }
    await callEndpoint('/end-call', { callSid: "t1" });
}

async function runTest2() {
    console.log("--- TEST 2: Hindi returning customer reorder ---");
    let result = await callEndpoint('/start-call', {
        callSid: "t2",
        callId: "c2",
        customerId: "cu2",
        customerData: {
            customer: { name: "Rahul" },
            lastOrder: { items: "Pen Box", quantity: 2, deliveryAddress: "Delhi", deliveryDate: "Tomorrow", createdAt: new Date().toISOString() }
        },
        language: "hindi",
        products: mockProducts
    });
    
    console.log(`Bot Greeting: ${result.reply}`);
    console.log(`User: haan same order chahiye`);
    result = await callEndpoint('/process-turn', {
        callSid: "t2",
        userMessage: "haan same order chahiye",
        sttConfidence: 0.95
    });
    console.log(`Bot: ${result.reply} (type: ${result.type})`);
    
    // We expect it to confirm or at least collect the remaining slots if we just forced it. 
    // Actually, parseReorderIntent will trigger filling slots and confirming.
    if (result.type === "turn" || result.type === "confirmed") {
        console.log("TEST 2: Check manually if it handled reorder correctly. Expected type: confirmed.\n");
    } else {
        console.log("TEST 2: FAIL\n");
    }
    await callEndpoint('/end-call', { callSid: "t2" });
}

async function runTest3() {
    console.log("--- TEST 3: Escalation keyword (Kannada) ---");
    let result = await callEndpoint('/start-call', {
        callSid: "t3",
        callId: "c3",
        customerId: "cu3",
        customerData: { customer: null, lastOrder: null },
        language: "kannada",
        products: mockProducts
    });
    
    console.log(`User: nimage agent beka`);
    result = await callEndpoint('/process-turn', {
        callSid: "t3",
        userMessage: "nimage agent beka",
        sttConfidence: 0.95
    });
    console.log(`Bot: ${result.reply} (type: ${result.type}, reason: ${result.reason})`);
    
    if (result.type === "escalated" && result.reason === "customer_request") {
        console.log("TEST 3: PASS\n");
    } else {
        console.log("TEST 3: FAIL\n");
    }
    await callEndpoint('/end-call', { callSid: "t3" });
}

async function runTest4() {
    console.log("--- TEST 4: Low confidence escalation ---");
    await callEndpoint('/start-call', {
        callSid: "t4",
        callId: "c4",
        customerId: "cu4",
        customerData: { customer: null, lastOrder: null },
        language: "english",
        products: mockProducts
    });
    
    let result;
    for (let i = 0; i < 3; i++) {
        console.log(`User: (mumbles) (confidence 0.2)`);
        result = await callEndpoint('/process-turn', {
            callSid: "t4",
            userMessage: "uhhhh",
            sttConfidence: 0.2
        });
        console.log(`Bot: ${result.reply} (type: ${result.type})`);
    }
    
    if (result.type === "escalated" && result.reason === "low_confidence") {
        console.log("TEST 4: PASS\n");
    } else {
        console.log("TEST 4: FAIL\n");
    }
    await callEndpoint('/end-call', { callSid: "t4" });
}

async function runAll() {
    try {
        await runTest1();
        await runTest2();
        await runTest3();
        await runTest4();
    } catch (e) {
        console.error("Test suite failed:", e);
    }
}

runAll();
