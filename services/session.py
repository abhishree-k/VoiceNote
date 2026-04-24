from typing import Dict, List, Optional
from pydantic import BaseModel

class CallSession(BaseModel):
    call_sid: str
    phone_number: str
    language: Optional[str] = None
    conversation_history: List[Dict[str, str]] = []
    order_buffer: List[str] = []
    is_returning_customer: bool = False
    escalation_flag: bool = False
    customer_name: Optional[str] = None
    last_order: Optional[str] = None

class SessionStore:
    """
    In-memory session management, scoped to individual calls.
    Keyed by call_sid.
    """
    def __init__(self):
        self._sessions: Dict[str, CallSession] = {}

    def create_session(self, call_sid: str, phone_number: str) -> CallSession:
        session = CallSession(call_sid=call_sid, phone_number=phone_number)
        self._sessions[call_sid] = session
        return session
    
    def get_session(self, call_sid: str) -> Optional[CallSession]:
        return self._sessions.get(call_sid)
    
    def update_session(self, call_sid: str, session: CallSession):
        self._sessions[call_sid] = session

    def end_session(self, call_sid: str):
        if call_sid in self._sessions:
            del self._sessions[call_sid]

# Singleton instance for the app
session_store = SessionStore()
