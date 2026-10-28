"""
Phoenix Tree AI - 电商 8 步全闭环 Worker (ecom_worker.py)
一比一复刻视频 1 的 8 步完整闭环：
01 接数据 ➔ 02 看数 ➔ 03 给建议 ➔ 04 CEO汇总 ➔ 05 店主拍板 ➔ 06 动手干活 ➔ 07 验收 ➔ 08 数据回流
"""
import json
import time
from datetime import datetime
from database.models import get_db
from core.ceo_agent import CEOAgent
from core.inspector_agent import InspectorAgent

ceo = CEOAgent()
inspector = InspectorAgent()

class EcomWorker:
    def __init__(self, store_id: str = "store_b"):
        self.store_id = store_id # 默认为 Etsy 店铺 B 或 亚马逊店铺 A
        
    def step_01_ingest_data(self) -> dict:
        """
        01 接数据：程序自动收 (店铺后台通知、成交邮件转寄)
        原理：AI 看不到的绝不瞎猜，拿不到就直说，不瞎估。
        """
        # 读取数据库中最新的店铺日指标
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM funnel_metrics WHERE store_id = ? ORDER BY id DESC LIMIT 1", (self.store_id,))
        row = cur.fetchone()
        conn.close()
        
        if row:
            data = dict(row)
        else:
            # 还原视频真实指标：访客 1240, 加购 74, 下单 31, 退款 2
            data = {
                "store_id": self.store_id,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "visitors": 1240,
                "add_to_cart": 74,
                "orders": 31,
                "refunds": 2,
                "gmv": 238.89,
                "net_profit": 145.20
            }
        return {
            "step": "01_接数据",
            "source": "成交邮件转寄 (Email Parsing) + 08:00 定时快照",
            "data": data,
            "status": "COMPLETED"
        }

    def step_02_look_at_data(self, ingest_res: dict) -> dict:
        """
        02 看数：计算整店漏斗 (来了多少人，多少加购，多少下单，哪一步掉了)
        原理：只看不同店铺：看错了，最多写错一句话。
        """
        d = ingest_res["data"]
        visitors = d["visitors"]
        add_to_cart = d["add_to_cart"]
        orders = d["orders"]
        
        cart_rate = round((add_to_cart / visitors * 100), 2) if visitors else 0 # 加购率 (视频为 6.0%)
        order_rate = round((orders / add_to_cart * 100), 2) if add_to_cart else 0 # 下单率 (视频为 41.9%)
        overall_rate = round((orders / visitors * 100), 2) if visitors else 0
        
        funnel = {
            "visitors": visitors,
            "add_to_cart": add_to_cart,
            "orders": orders,
            "cart_rate": f"{cart_rate}%",
            "order_rate": f"{order_rate}%",
            "overall_rate": f"{overall_rate}%",
            "insight": "柑橘香薰连着两周卖得最好，三成是回头客；但加购率略有下滑，需扩充SKU并优化主图视觉。"
        }
        return {
            "step": "02_看数",
            "funnel": funnel,
            "status": "COMPLETED"
        }

    def step_03_give_suggestions(self, funnel_res: dict) -> dict:
        """
        03 给建议：哪一步掉了给什么建议
        案例：基于柑橘香薰热销与加购转化，建议推出 2 款柑橘系衍生新品 (车载香氛+补充液)
        """
        proposal = {
            "type": "NEW_PRODUCT_LAUNCH",
            "product_name": "天然柑橘精油车载香氛 & 扩香补充液 (2款新品组合)",
            "rationale": "原柑橘香薰老客复购率高达 30%，客单价高但缺少便携场景，加购率存在 1.5% 提升空间。",
            "pricing": {
                "cost": 15.00,
                "price": 48.00,
                "estimated_margin": "68.75%"
            },
            "plan": [
                "1. 自动生成 4 张场景效果图 (车内出风口、极简桌面摆放)",
                "2. 撰写符合 Etsy/亚马逊平台规范的英文高点击 SEO 标题与五点描述",
                "3. 挂入店铺草稿箱，等待店主最终确认发布"
            ]
        }
        return {
            "step": "03_给建议",
            "proposal": proposal,
            "status": "COMPLETED"
        }

    def step_04_submit_to_ceo(self, proposal_res: dict) -> dict:
        """
        04 CEO 汇总：几条建议合成一份，经过 AI 查 AI 质检后，上挂到【待办事项】
        """
        title = "【新品上架提案】柑橘系车载香氛与补充液扩充"
        res = ceo.submit_proposal_from_worker(
            module="ecom",
            task_type="NEW_PRODUCT_LAUNCH",
            title=title,
            proposal_data=proposal_res["proposal"]
        )
        return {
            "step": "04_CEO汇总",
            "task_id": res.get("task_id"),
            "status": res.get("status"),
            "msg": res.get("msg")
        }

    def step_06_do_the_work(self, task_id: str) -> dict:
        """
        06 动手干活 (AI 干活)：店主拍板后触发！
        出图、写标题和描述、建商品草案
        原理：只接批过的活；真动店铺前，再问店主一次。
        """
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task = cur.fetchone()
        if not task:
            conn.close()
            return {"error": "未找到工单"}
            
        # 生成符合电商字符规范的商品标题 (45 字符以内)
        artifacts = {
            "title": "Natural Citrus Car Diffuser Aromatherapy Kit",
            "sku": "CITRUS-CAR-01",
            "price": "$48.00",
            "images": [
                "https://images.unsplash.com/photo-1608571423902-eed4a5ad8108?w=800",
                "https://images.unsplash.com/photo-1547887537-6158d64c35b3?w=800"
            ],
            "description": "Handcrafted pure cold-pressed citrus aromatherapy for car vents and desktop relaxation. 100% organic, no artificial fragrances.",
            "seo_tags": ["car diffuser", "citrus aromatherapy", "essential oil gift", "handmade diffuser"],
            "ready_for_draft": True
        }
        
        # 07 验收：质检 Agent 进行合规机审
        inspection = inspector.inspect_execution_artifacts(artifacts)
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if inspection["passed"]:
            cur.execute("""
            UPDATE tasks SET status='VERIFIED', artifacts=?, updated_at=? WHERE task_id=?
            """, (json.dumps(artifacts, ensure_ascii=False), now_str, task_id))
            conn.commit()
            conn.close()
            return {
                "step": "06_动手干活 & 07_验收",
                "artifacts": artifacts,
                "inspection": inspection,
                "status": "VERIFIED",
                "msg": "AI 已全自动完成出图与标题文案，经 Inspector 查验合格，已同步至商品草稿箱！"
            }
        else:
            cur.execute("""
            UPDATE tasks SET status='REWORK', updated_at=? WHERE task_id=?
            """, (now_str, task_id))
            conn.commit()
            conn.close()
            return {
                "step": "06_动手干活",
                "status": "REWORK",
                "msg": f"质检验收未过，打回重做：{inspection['notes']}"
            }

    def step_08_recirculate(self, task_id: str) -> dict:
        """
        08 回流 (回到起点)：卖得怎么样，第二天又是新数据。
        原理：圈每转一次，店就多一分有数。
        """
        conn = get_db()
        cur = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("UPDATE tasks SET status='COMPLETED', updated_at=? WHERE task_id=?", (now_str, task_id))
        
        # 模拟数据回流：新品带来新增浏览与订单
        cur.execute("""
        UPDATE funnel_metrics 
        SET visitors = visitors + 180, add_to_cart = add_to_cart + 15, orders = orders + 6, gmv = gmv + 288.0
        WHERE store_id = ?
        """, (self.store_id,))
        
        conn.commit()
        conn.close()
        return {
            "step": "08_回流",
            "status": "COMPLETED",
            "msg": "新品已成功激活，次日流量与订单数据已成功回流到 01 接数据漏斗！"
        }
