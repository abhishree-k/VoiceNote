from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from routers import customer, call, order, escalation, product

app = FastAPI(title="Automaton AI Voice Bot Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )

app.include_router(customer.router)
app.include_router(call.router)
app.include_router(order.router)
app.include_router(escalation.router)
app.include_router(product.router)

@app.get("/")
def read_root():
    return {"message": "Automaton AI Backend is running. Access /docs for API documentation."}
