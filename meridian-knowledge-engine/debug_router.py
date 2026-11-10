import asyncio
from app.core.answer.router import CalculatorRouter

async def test():
    router = CalculatorRouter()
    route_type, inputs = router.route(
        "PO price 395, invoice 400 for 500 bags. Pass or variance?",
        "Arvana Infra",
        "2026-08-01"
    )
    print(f"route_type: {route_type}")
    print(f"inputs: {inputs}")

asyncio.run(test())