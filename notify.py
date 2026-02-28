#!/usr/bin/env python3
"""
Economic News 实时通知脚本
监听 SSE，有新快讯立即通过 OpenClaw 发送给用户
"""

import asyncio
import json
import sys
import httpx

SERVICE_URL = "http://localhost:8765"

async def send_notification(message: str, target: str, channel: str = "feishu"):
    """通过 OpenClaw CLI 发送通知"""
    import subprocess
    cmd = ["openclaw", "message", "send", "--channel", channel, "--target", target, "--message", message]
    subprocess.run(cmd, capture_output=True)

async def listen_sse(target: str, channel: str = "feishu", important_only: bool = False):
    """监听 SSE 并发送通知"""
    print(f"开始监听 Economic News 快讯...")
    print(f"目标: {channel}:{target}")
    print(f"仅重要: {important_only}")
    print("-" * 40)
    
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", f"{SERVICE_URL}/events?history=false") as response:
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    event_str, buffer = buffer.split("\n\n", 1)
                    
                    # 解析事件
                    event_type = None
                    event_data = None
                    
                    for line in event_str.split("\n"):
                        if line.startswith("event:"):
                            event_type = line[6:].strip()
                        elif line.startswith("data:"):
                            try:
                                event_data = json.loads(line[5:].strip())
                            except:
                                pass
                    
                    if event_type == "flash" and event_data:
                        # 检查是否只要重要消息
                        if important_only and not event_data.get("important"):
                            continue
                        
                        # 格式化消息
                        importance = "🔴 " if event_data.get("important") else ""
                        msg = f"{importance}【金十快讯】{event_data.get('title', '')}\n\n{event_data.get('content', '')}\n\n{event_data.get('time', '')}"
                        
                        print(f"[{event_data.get('time')}] 发送通知...")
                        await send_notification(msg, target, channel)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Economic News 实时通知")
    parser.add_argument("-t", "--target", required=True, help="目标用户/群组 ID")
    parser.add_argument("-c", "--channel", default="feishu", help="通知渠道 (feishu/telegram/discord)")
    parser.add_argument("--important", action="store_true", help="仅通知重要快讯")
    args = parser.parse_args()
    
    try:
        asyncio.run(listen_sse(args.target, args.channel, args.important))
    except KeyboardInterrupt:
        print("\n停止监听")
