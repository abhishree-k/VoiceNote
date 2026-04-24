import express from 'express';
import 'dotenv/config';
import { startCall, processCall, endCall } from './agent.service.js';
import { getAllSessions } from './services/session.service.js';

const app = express();
const port = process.env.PORT || 4000;

app.use(express.json());

// CORS allow all
app.use((req, res, next) => {
    res.header("Access-Control-Allow-Origin", "*");
    res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept");
    next();
});

app.post('/agent/start-call', async (req, res, next) => {
    try {
        const { callSid, callId, customerId, customerData, language, products } = req.body;
        const result = await startCall({ callSid, callId, customerId, customerData, language, products });
        res.json(result);
    } catch (error) {
        next(error);
    }
});

app.post('/agent/process-turn', async (req, res, next) => {
    try {
        const { callSid, userMessage, sttConfidence } = req.body;
        const result = await processCall({ callSid, userMessage, sttConfidence });
        res.json(result);
    } catch (error) {
        next(error);
    }
});

app.post('/agent/end-call', async (req, res, next) => {
    try {
        const { callSid } = req.body;
        const result = await endCall({ callSid });
        res.json(result);
    } catch (error) {
        next(error);
    }
});

app.get('/health', (req, res) => {
    res.json({ status: "ok", activeSessions: getAllSessions().size });
});

// Global error handler
app.use((err, req, res, next) => {
    console.error(err);
    res.status(500).json({ error: err.message, type: "AGENT_ERROR" });
});

app.listen(port, () => {
    console.log(`Agent service listening on port ${port}`);
});
