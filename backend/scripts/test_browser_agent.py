import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.agents.price_execution_agent import execute_price_change

async def main():
    print("Testing Browser Use AI Agent (Phase 4)...")
    
    product_name = "Klypup Premium Subscription"
    new_price = 149.00
    # Using a dummy testing target since we don't have real credentials
    platform_url = "https://www.example.com" 
    
    print(f"\nCommanding AI to navigate to {platform_url} and set price of '{product_name}' to {new_price}...")
    print("Watch the browser window that appears!\n")
    
    try:
        result = await execute_price_change(
            product_name=product_name,
            new_price=new_price,
            platform_url=platform_url
        )
        print(f"\nFinal Result: {result}")
            
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    # Make sure you set OPENAI_API_KEY in your environment before running this!
    asyncio.run(main())
