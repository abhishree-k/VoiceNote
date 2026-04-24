# Automaton AI Voice Bot Backend

This is the FastAPI backend for the Automaton AI Voice Bot hackathon project. It connects seamlessly to the Supabase database. All endpoints return clean JSON and expect JSON payloads.

## Running the Server
Ensure you have set `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in the `.env` file. Then start the server on port 8000:
`source venv/bin/activate`
`uvicorn main:app --reload --port 8000`

## API Endpoints Documentation

### Customer Endpoints
1. **`POST /api/customer/lookup`**
   - **Use case:** Person 1 (Twilio voice pipeline) calls this at the very start of every incoming call.
   - **Receives:** `{"phone_number": "+919876543210"}`
   - **Returns:** Customer object (`id`, `phone_number`, `name`, `preferred_lang`, etc.). Includes `is_new_customer: true` if newly created. If returning, also includes `last_orders: [ ... ]` representing the last 3 orders and their items.

2. **`GET /api/customers`**
   - **Use case:** Person 4 dashboard list view.
   - **Returns:** Array of all customers along with their `total_orders` and `last_called_at`.

3. **`GET /api/customer/{customer_id}`**
   - **Use case:** Person 4 dashboard single customer profile.
   - **Returns:** Customer profile including all past orders and order items under `orders: [ ... ]`.

### Call Endpoints
4. **`POST /api/call/start`**
   - **Use case:** Person 1 calls this when call begins.
   - **Receives:** `{"customer_id": "uuid", "twilio_call_sid": "CA123..."}`
   - **Returns:** Call object with `status="active"` and `id` (call ID).

5. **`POST /api/call/update-transcript`**
   - **Use case:** Person 2 (AI Agent) calls this after every conversation turn.
   - **Receives:** `{"call_id": "uuid", "entry": {"role": "bot", "message": "hello"}}`
   - **Returns:** Updated call object.

6. **`POST /api/call/end`**
   - **Use case:** Person 1 calls this when call ends.
   - **Receives:** `{"call_id": "uuid", "final_status": "completed", "language_used": "en"}`
   - **Returns:** Updated call object. Note: this also automatically updates the customer's `preferred_lang`.

7. **`GET /api/calls`**
   - **Use case:** Person 4 dashboard (recent 10 calls).
   - **Returns:** Last 10 calls, including joined customer name and phone.

8. **`GET /api/call/{call_id}`**
   - **Use case:** Person 4 clicking on a call.
   - **Returns:** Call details with raw transcript and associated `order` along with order `items`.

### Order Endpoints
9. **`POST /api/order/create`**
   - **Use case:** Person 2 starts conversation order phase.
   - **Receives:** `{"customer_id": "uuid", "call_id": "uuid"}`
   - **Returns:** New order object with `status="pending"`.

10. **`POST /api/order/add-item`**
    - **Use case:** Person 2 adding item to order.
    - **Receives:** `{"order_id": "uuid", "item_name": "Burger", "quantity": 2, "unit_price": 5.99}`
    - **Returns:** Parent order object containing the newly updated total (handled automatically by Supabase trigger).

11. **`POST /api/order/update-item`**
    - **Use case:** Person 2 changes quantity mid-conversation.
    - **Receives:** `{"order_id": "uuid", "item_name": "Burger", "new_quantity": 3}`
    - **Returns:** Parent order object (with updated total).

12. **`POST /api/order/confirm`**
    - **Use case:** Person 2 finishes order flow.
    - **Receives:** `{"order_id": "uuid"}`
    - **Returns:** The confirmed order enriched with all items. Also updates `total_orders` on the customer.

13. **`POST /api/order/cancel`**
    - **Use case:** Person 2 detects user hang up or cancel.
    - **Receives:** `{"order_id": "uuid"}`
    - **Returns:** Cancelled order.

14. **`GET /api/orders`**
    - **Use case:** Person 4 dashboard.
    - **Returns:** All orders, items, and linked customer details.

### Escalation Endpoints
15. **`POST /api/escalation/create`**
    - **Use case:** Person 2 cannot handle the call confidently.
    - **Receives:** `{"call_id": "uuid", "customer_id": "uuid", "reason": "low_confidence"}`
    - **Returns:** The escalation row. Also updates Call `status` to `escalated`.

16. **`POST /api/escalation/resolve`**
    - **Use case:** Person 4 dashboard marks resolved.
    - **Receives:** `{"escalation_id": "uuid"}`
    - **Returns:** Resolves the escalation to true.

17. **`GET /api/escalations`**
    - **Use case:** Person 4 dashboard escalation inbox.
    - **Returns:** Array of unresolved escalations, joining call and customer context.

### Product Endpoints
18. **`GET /api/products`**
    - **Use case:** Person 2 to know current catalog.
    - **Returns:** Array of products where `is_available` is true.

19. **`POST /api/products`**
    - **Use case:** Person 4 adding new item.
    - **Receives:** `{"name": "Pizza", "price": 12.99, "sku": "PZ1"}`
    - **Returns:** New product.

20. **`PATCH /api/product/{product_id}`**
    - **Use case:** Person 4 updates price or toggles availability.
    - **Receives:** Optional partial updates like `{"price": 14.99}`
    - **Returns:** Updated product.
