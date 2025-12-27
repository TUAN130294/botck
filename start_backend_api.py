"""
Start VN-Quant API Backend on Port 8003
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "quantum_stock.web.vn_quant_api:app",
        host="0.0.0.0",
        port=8003,
        reload=False,  # Disable reload for stability
        log_level="info"
    )
