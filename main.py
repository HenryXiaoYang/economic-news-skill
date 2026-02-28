#!/usr/bin/env python3
"""
Economic News Service v4.3.0 - Playwright Edition
- 自动过滤 VIP 快讯
- 返回完整详情（无 URL）
- 新增搜索 API（VIP 仅返回标题）
"""

import asyncio
import json
import logging
import re
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional
from collections import deque
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from playwright.async_api import async_playwright, Page

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/tmp/economic_news.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

VERSION = "4.3.0"

class State:
    browser = None
    playwright = None
    page: Optional[Page] = None
    top_list: list = []
    top_list_details: dict = {}  # flash_id -> content 缓存
    flash_list: deque = deque(maxlen=200)
    classify_list: list = []
    trading_clock: dict = {}
    sse_clients: set = set()
    connected: bool = False
    last_update: Optional[datetime] = None

state = State()

def extract_title(content: str) -> str:
    if not content:
        return ""
    match = re.match(r'^(?:<b>)?(?:【)(?:<b>)?(.+?)(?:</b>)?(?:】)(?:</b>)?', content)
    if match:
        return match.group(1)
    return content[:50] if len(content) > 50 else content

def is_vip_flash(flash: dict) -> bool:
    """判断是否为 VIP 快讯"""
    # 检查 type 字段
    if flash.get('type') == 1:
        return True
    # 检查 vip 字段
    if flash.get('vip') == 1:
        return True
    # 检查 data.lock
    data = flash.get('data', {})
    if isinstance(data, dict) and data.get('lock'):
        return True
    # 检查 vip_level
    if data.get('vip_level', 0) > 0:
        return True
    return False

def parse_flash(flash: dict, filter_vip: bool = True) -> Optional[dict]:
    """解析快讯，filter_vip=True 时过滤 VIP 快讯"""
    if filter_vip and is_vip_flash(flash):
        return None
    
    data = flash.get('data', {})
    if isinstance(data, dict):
        content = data.get('content', '')
        title = data.get('title', '') or extract_title(content)
    else:
        content = ''
        title = flash.get('title', '')
    
    return {
        '_id': flash.get('id', ''),  # 内部用
        'time': flash.get('time', ''),
        'important': flash.get('important', 0) == 1,
        'title': title,
        'content': content,
    }

def parse_flash_for_search(flash: dict) -> Optional[dict]:
    """解析搜索结果中的快讯，过滤 VIP"""
    if is_vip_flash(flash):
        return None  # 直接过滤 VIP
    
    data = flash.get('data', {})
    
    if isinstance(data, dict):
        title = data.get('title', '') or flash.get('title', '')
        content = data.get('content', '')
    else:
        title = flash.get('title', '')
        content = ''
    
    return {
        'time': flash.get('time', flash.get('display_datetime', '')),
        'important': flash.get('important', 0) == 1,
        'title': title,
        'content': content,
    }

async def broadcast_sse(event_type: str, data: dict):
    if not state.sse_clients:
        return
    message = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    dead_clients = set()
    for queue in state.sse_clients:
        try:
            await queue.put(message)
        except:
            dead_clients.add(queue)
    state.sse_clients -= dead_clients

def get_market_status(market: dict) -> dict:
    name = market.get('name', '')
    start_time = market.get('startTime', '')
    end_time = market.get('endTime', '')
    utc_offset = market.get('utc', 0)
    rest_days = market.get('restDays', [])
    
    if isinstance(utc_offset, str):
        utc_offset = float(utc_offset)
    
    market_tz = timezone(timedelta(hours=utc_offset))
    market_now = datetime.now(market_tz)
    market_date = market_now.strftime('%Y-%m-%d')
    market_time = market_now.strftime('%H:%M')
    
    is_rest_day = any(r.get('day') == market_date for r in rest_days)
    is_weekend = market_now.weekday() >= 5
    
    def parse_time(t):
        h, m = map(int, t.split(':'))
        return h * 60 + m
    
    current_mins = parse_time(market_time)
    start_mins = parse_time(start_time)
    end_mins = parse_time(end_time)
    
    if end_mins < start_mins:
        is_trading = current_mins >= start_mins or current_mins < end_mins
    else:
        is_trading = start_mins <= current_mins < end_mins
    
    if is_rest_day or is_weekend:
        status = "休市"
        is_trading = False
    elif is_trading:
        status = "交易中"
    else:
        status = "已收盘"
    
    return {
        'name': name,
        'start_time': start_time,
        'end_time': end_time,
        'utc': utc_offset,
        'local_time': market_time,
        'local_date': market_date,
        'status': status,
        'is_trading': is_trading,
    }


async def fetch_toplist_details():
    """从 Flash API 获取 topList 详情"""
    if not state.top_list:
        return
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "x-app-id": "bVBF4FyRTn5NJF5n",
                "x-version": "1.0.0",
                "Origin": "https://www.economic_news.com"
            }
            
            for item in state.top_list:
                fid = item.get('flash_id', '')
                if fid and fid not in state.top_list_details:
                    # 用 max_id 获取该条及之前的快讯
                    url = f"https://flash-api.economic_news.com/get_flash_list?channel=-8200&vip=1&max_id={fid}"
                    resp = await client.get(url, headers=headers, timeout=10)
                    data = resp.json()
                    
                    for flash in data.get('data', []):
                        if flash.get('id') == fid:
                            flash_data = flash.get('data', {})
                            content_text = flash_data.get('content', '')
                            # 清理 HTML 标签
                            import re
                            content_text = re.sub(r'<[^>]+>', '', content_text)
                            state.top_list_details[fid] = content_text
                            break
            
            has_details = sum(1 for fid in [i.get('flash_id') for i in state.top_list] if state.top_list_details.get(fid))
            logger.info(f"TopList details fetched: {has_details}/{len(state.top_list)}")
    except Exception as e:
        logger.warning(f"Failed to fetch toplist details: {e}")

async def load_trading_clock():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://cdn.economic_news.com/trading-clock/new/data.json", timeout=10)
            data = resp.json()
            state.trading_clock = data.get('data', {})
            markets = []
            for group in state.trading_clock.get('datas', []):
                if isinstance(group, list):
                    markets.extend(group)
            logger.info(f"Trading clock loaded: {len(markets)} markets")
    except Exception as e:
        logger.error(f"Failed to load trading clock: {e}")

GET_DATA_JS = """
() => {
    function findInTree(vm, key, depth=0) {
        if (depth > 6) return null;
        if (vm[key] && Array.isArray(vm[key]) && vm[key].length > 0) return vm[key];
        if (vm.$children) {
            for (const c of vm.$children) {
                const r = findInTree(c, key, depth+1);
                if (r) return r;
            }
        }
        return null;
    }
    
    const app = document.querySelector('#app').__vue__;
    const store = app.$store.state;
    
    return JSON.stringify({
        topList: store.topListItems || [],
        flashs: findInTree(app, 'flashs') || [],
        classifyList: findInTree(app, 'classifyList') || []
    });
}
"""

async def poll_data():
    while True:
        await asyncio.sleep(3)
        if not state.page or not state.connected:
            continue
        
        try:
            result = await state.page.evaluate(GET_DATA_JS)
            data = json.loads(result)
            
            new_top_list = data.get('topList', [])
            if new_top_list and new_top_list != state.top_list:
                state.top_list = new_top_list
                state.last_update = datetime.now()
                # 缓存 topList 的详情
                for item in new_top_list:
                    fid = item.get('flash_id', '')
                    if fid and fid not in state.top_list_details:
                        # 从 flash_list 里找详情
                        for f in state.flash_list:
                            if f['id'] == fid:
                                state.top_list_details[fid] = f.get('content', '')
                                break
                logger.info(f"TopList updated: {len(state.top_list)} items")
                asyncio.create_task(fetch_toplist_details())
                await broadcast_sse('toplist', {'items': state.top_list})
            
            classify_list = data.get('classifyList', [])
            if classify_list and classify_list != state.classify_list:
                state.classify_list = classify_list
                logger.info(f"ClassifyList updated: {len(state.classify_list)} categories")
            
            flashs = data.get('flashs', [])
            if flashs:
                existing_ids = {f['id'] for f in state.flash_list}
                new_count = 0
                for flash in reversed(flashs):
                    flash_id = flash.get('id', '')
                    if flash_id and flash_id not in existing_ids:
                        parsed = parse_flash(flash, filter_vip=True)
                        if parsed:  # 非 VIP 快讯
                            state.flash_list.appendleft(parsed)
                            new_count += 1
                            await broadcast_sse('flash', parsed)
                
                if new_count > 0:
                    logger.info(f"Added {new_count} new flash items (VIP filtered)")
                    
        except Exception as e:
            logger.warning(f"Poll error: {e}")

async def start_browser():
    logger.info("Starting Playwright browser...")
    
    await load_trading_clock()
    
    state.playwright = await async_playwright().start()
    state.browser = await state.playwright.chromium.launch(
        headless=True,
        args=['--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage']
    )
    
    context = await state.browser.new_context(
        viewport={'width': 800, 'height': 600},
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    )
    
    state.page = await context.new_page()
    
    logger.info("Loading economic_news.com...")
    await state.page.goto("https://www.economic_news.com/", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(8)
    
    try:
        result = await state.page.evaluate(GET_DATA_JS)
        data = json.loads(result)
        
        state.top_list = data.get('topList', [])
        state.classify_list = data.get('classifyList', [])
        logger.info(f"Initial TopList: {len(state.top_list)} items")
        logger.info(f"Initial ClassifyList: {len(state.classify_list)} categories")
        
        flashs = data.get('flashs', [])
        vip_count = 0
        for flash in reversed(flashs):
            parsed = parse_flash(flash, filter_vip=True)
            if parsed:
                state.flash_list.appendleft(parsed)
            else:
                vip_count += 1
        logger.info(f"Initial Flash: {len(state.flash_list)} items (filtered {vip_count} VIP)")
        
    except Exception as e:
        logger.error(f"Failed to get initial data: {e}")
    
    state.connected = True
    state.last_update = datetime.now()
    logger.info("Browser connected successfully")
    
    # 获取 topList 详情
    await fetch_toplist_details()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Economic News Service v{VERSION} starting...")
    asyncio.create_task(start_browser())
    asyncio.create_task(poll_data())
    yield
    if state.browser:
        await state.browser.close()
    if state.playwright:
        await state.playwright.stop()
    logger.info("Service stopped")

app = FastAPI(title="Economic News", version=VERSION, lifespan=lifespan)

@app.get("/")
async def index():
    return {
        "service": "Economic News",
        "version": VERSION,
        "connected": state.connected,
        "last_update": state.last_update.isoformat() if state.last_update else None,
        "top_list_count": len(state.top_list),
        "flash_count": len(state.flash_list),
        "classify_count": len(state.classify_list),
        "sse_clients": len(state.sse_clients),
    }

@app.get("/events")
async def sse_events(request: Request):
    async def event_generator():
        queue = asyncio.Queue()
        state.sse_clients.add(queue)
        try:
            if state.top_list:
                yield f"event: toplist\ndata: {json.dumps({'items': state.top_list}, ensure_ascii=False)}\n\n"
            for flash in list(state.flash_list)[:20]:
                yield f"event: flash\ndata: {json.dumps(flash, ensure_ascii=False)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    yield message
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            state.sse_clients.discard(queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )

@app.get("/top10")
async def get_top10():
    """获取重要事件 Top10，包含详情"""
    # 优先从缓存获取，其次从 flash_list
    flash_map = {f['_id']: f.get('content', '') for f in state.flash_list}
    
    items = []
    for item in state.top_list:
        flash_id = item.get('flash_id', '')
        # 优先用缓存
        content = state.top_list_details.get(flash_id) or flash_map.get(flash_id, '')
        
        title = item.get('title', '')
        items.append({
            'rank': len(items) + 1,
            'title': title,
            'content': content if content else title,
            'time': item.get('display_time', ''),
        })
    
    return JSONResponse({
        "success": True,
        "count": len(items),
        "items": items,
        "updated": state.last_update.isoformat() if state.last_update else None,
    })

@app.get("/latest")
async def get_latest(limit: int = 50, channel: int = None):
    limit = min(limit, 200)
    items = list(state.flash_list)
    if channel is not None:
        items = [f for f in items if channel in f.get('channel', [])]
    # 去掉内部 _id
    clean_items = [{k:v for k,v in f.items() if k != '_id'} for f in items[:limit]]
    return JSONResponse({
        "success": True,
        "count": len(items),
        "items": clean_items,
    })

def clean_category(cat):
    """移除 isNew 字段"""
    result = {'id': cat.get('id'), 'name': cat.get('name')}
    if cat.get('child'):
        result['child'] = [{'id': c.get('id'), 'name': c.get('name')} for c in cat.get('child', [])]
    return result

@app.get("/categories")
async def get_categories():
    cleaned = [clean_category(c) for c in state.classify_list]
    return JSONResponse({
        "success": True,
        "count": len(cleaned),
        "items": cleaned,
    })

@app.get("/category/{category_id}")
async def get_by_category(category_id: int, limit: int = 50):
    limit = min(limit, 200)
    items = [f for f in state.flash_list if category_id in f.get('channel', [])]
    
    category_name = None
    for cat in state.classify_list:
        if cat.get('id') == category_id:
            category_name = cat.get('name')
            break
        for child in cat.get('child', []):
            if child.get('id') == category_id:
                category_name = child.get('name')
                break
    
    clean_items = [{k:v for k,v in f.items() if k != '_id'} for f in items[:limit]]
    return JSONResponse({
        "success": True,
        "category_id": category_id,
        "category_name": category_name,
        "count": len(clean_items),
        "items": clean_items,
    })

@app.get("/search")
async def search(q: str, limit: int = 20):
    """搜索快讯，VIP 快讯仅返回标题"""
    if not q or len(q.strip()) == 0:
        return JSONResponse({"success": False, "error": "搜索关键词不能为空"}, status_code=400)
    
    limit = min(limit, 100)
    
    try:
        # 创建新页面进行搜索
        context = await state.browser.new_context()
        search_page = await context.new_page()
        
        search_url = f"https://search.economic_news.com/?keyword={quote(q)}"
        await search_page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(3)
        
        # 获取搜索结果
        result = await search_page.evaluate("""
            () => {
                function findFlashList(vm, depth=0) {
                    if (depth > 8) return null;
                    if (vm.flashList && Array.isArray(vm.flashList)) return vm.flashList;
                    if (vm.$children) {
                        for (const c of vm.$children) {
                            const r = findFlashList(c, depth+1);
                            if (r) return r;
                        }
                    }
                    return null;
                }
                const app = document.querySelector('#app');
                if (!app || !app.__vue__) return JSON.stringify([]);
                return JSON.stringify(findFlashList(app.__vue__) || []);
            }
        """)
        
        await search_page.close()
        await context.close()
        
        flash_list = json.loads(result)
        
        # 解析结果，过滤 VIP
        items = []
        for flash in flash_list:
            parsed = parse_flash_for_search(flash)
            if parsed:
                items.append(parsed)
                if len(items) >= limit:
                    break
        
        return JSONResponse({
            "success": True,
            "keyword": q,
            "count": len(items),
            "items": items,
        })
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/clock")
async def get_trading_clock(trading_only: bool = False):
    markets = []
    for group in state.trading_clock.get('datas', []):
        if isinstance(group, list):
            for market in group:
                if isinstance(market, dict):
                    status = get_market_status(market)
                    if trading_only and not status['is_trading']:
                        continue
                    markets.append(status)
    
    status_order = {'交易中': 0, '已收盘': 1, '休市': 2}
    markets.sort(key=lambda x: status_order.get(x['status'], 9))
    
    return JSONResponse({
        "success": True,
        "count": len(markets),
        "server_time": datetime.now().isoformat(),
        "markets": markets,
    })

@app.get("/clock/{market_name}")
async def get_market_clock(market_name: str):
    for group in state.trading_clock.get('datas', []):
        if isinstance(group, list):
            for market in group:
                if isinstance(market, dict) and market_name in market.get('name', ''):
                    return JSONResponse({
                        "success": True,
                        **get_market_status(market),
                    })
    
    return JSONResponse({"success": False, "error": "Market not found"}, status_code=404)

@app.get("/health")
async def health():
    return {"status": "ok", "connected": state.connected}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
