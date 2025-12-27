"""
Test WebSocket connection and display agent messages
"""
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8001/ws/autonomous"

    print("=" * 70)
    print("CONNECTING TO WEBSOCKET...")
    print(f"URI: {uri}")
    print("=" * 70)
    print()

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            print("Listening for messages...")
            print()

            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get('type', 'unknown')

                print(f"\n{'='*70}")
                print(f"📨 Message Type: {msg_type}")
                print(f"{'='*70}")

                if msg_type == 'agent_discussion':
                    print(f"\n📊 Symbol: {data.get('symbol')}")
                    print(f"Source: {data.get('source')}")
                    print(f"\n🗨️ Agent Messages:")

                    for msg in data.get('messages', []):
                        agent = msg.get('agent_name', 'Unknown')
                        emoji = msg.get('agent_emoji', '🤖')
                        content = msg.get('content', '')
                        confidence = msg.get('confidence', 0)

                        print(f"\n  {emoji} {agent} (Confidence: {confidence*100:.0f}%):")
                        print(f"     {content}")

                    verdict = data.get('verdict')
                    if verdict:
                        print(f"\n  ⚖️ VERDICT:")
                        print(f"     Signal: {verdict.get('signal_type')}")
                        print(f"     Confidence: {verdict.get('confidence'):.1f}%")
                        print(f"     Reasoning: {verdict.get('reasoning')}")

                elif msg_type == 'order_executed':
                    print(f"\n💰 ORDER EXECUTED:")
                    print(f"   {data.get('action')} {data.get('quantity'):,} {data.get('symbol')} @ {data.get('price')} VND")

                elif msg_type == 'position_exited':
                    print(f"\n🔄 POSITION EXITED:")
                    print(f"   {data.get('symbol')} - {data.get('exit_reason')}")
                    print(f"   P&L: {data.get('pnl'):,.0f} VND ({data.get('pnl_pct')*100:.2f}%)")

                elif msg_type == 'status_update':
                    print(f"\n📊 STATUS UPDATE:")
                    print(f"   Portfolio: {data.get('portfolio_value', 0):,.0f} VND")
                    print(f"   Positions: {data.get('active_positions', 0)}")

                else:
                    print(json.dumps(data, indent=2))

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure server is running:")
        print("   python run_autonomous_paper_trading.py")

if __name__ == "__main__":
    asyncio.run(test_websocket())
