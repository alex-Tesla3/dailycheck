"""AI 健康分析：汇总用户近期数据，调用 OpenAI 兼容的大模型接口生成个性化建议。"""
import json
from datetime import timedelta

import requests
from fastapi import HTTPException

from .config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from .dates import today_date, utc_now_str

SYSTEM_PROMPT = """你是一名贴心的健康习惯教练，负责基于用户的真实打卡与健康数据给出个性化建议。
规则：
1. 只根据提供的数据说话，不要编造数据；
2. 如果血压/体重有异常趋势，明确提示，但必须说明"以上仅供参考，不能替代医生诊断"；
3. 给出 3-5 条具体、可执行、针对该用户实际情况的改进建议；
4. 用中文和 Markdown 输出，结构为：### 总体评价 / ### 做得好的地方 / ### 需要注意 / ### 改进建议；
5. 语气温和、鼓励，避免说教。"""


def _fmt_value(value):
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value or "")


def build_summary(db, user_id: int, days: int) -> str:
    today = today_date()
    start = today - timedelta(days=days - 1)
    start_str = start.strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    lines = [f"用户近 {days} 天（{start_str} 至 {today_str}）的数据如下：", ""]

    # 习惯打卡
    habits = db.execute(
        "SELECT * FROM habits WHERE user_id = ? ORDER BY sort_order, id", (user_id,)
    ).fetchall()
    lines.append("【习惯打卡】")
    if not habits:
        lines.append("- 暂无习惯")
    for h in habits:
        rows = db.execute(
            "SELECT date, value FROM checkins WHERE user_id = ? AND habit_id = ? AND done = 1 AND date >= ? AND date <= ?",
            (user_id, h["id"], start_str, today_str),
        ).fetchall()
        done = len(rows)
        total_values = []
        for r in rows:
            if r["value"]:
                try:
                    total_values.append(float(r["value"]))
                except ValueError:
                    pass
        line = f"- {h['name']}：完成 {done}/{days} 天"
        if total_values:
            unit = h["value_label"] or ""
            line += f"，累计约 {sum(total_values):g}{unit}"
        lines.append(line)

    # 血压
    bp_rows = db.execute(
        "SELECT * FROM blood_pressure WHERE user_id = ? AND measured_at >= ? AND measured_at <= ? ORDER BY measured_at",
        (user_id, f"{start_str} 00:00:00", f"{today_str} 23:59:59"),
    ).fetchall()
    lines.append("")
    lines.append("【血压】")
    if not bp_rows:
        lines.append("- 近段无血压记录")
    else:
        sys_vals = [r["systolic"] for r in bp_rows]
        dia_vals = [r["diastolic"] for r in bp_rows]
        high = sum(1 for r in bp_rows if r["systolic"] >= 140 or r["diastolic"] >= 90)
        lines.append(f"- 记录 {len(bp_rows)} 次，平均 {sum(sys_vals)/len(sys_vals):.0f}/{sum(dia_vals)/len(dia_vals):.0f} mmHg")
        lines.append(f"- 偏高（≥140/90）次数：{high}")
        if len(bp_rows) >= 2:
            lines.append(f"- 收缩压从 {bp_rows[0]['systolic']} 到 {bp_rows[-1]['systolic']}，舒张压从 {bp_rows[0]['diastolic']} 到 {bp_rows[-1]['diastolic']}")

    # 指标（体重等）
    metric_rows = db.execute(
        "SELECT * FROM metrics WHERE user_id = ? AND date >= ? AND date <= ? ORDER BY date, id",
        (user_id, start_str, today_str),
    ).fetchall()
    lines.append("")
    lines.append("【体重等指标】")
    by_name = {}
    for r in metric_rows:
        by_name.setdefault(r["name"], []).append(r)
    if not by_name:
        lines.append("- 近段无指标记录")
    for name, rows in by_name.items():
        unit = rows[0]["unit"] or ""
        latest = rows[-1]
        if len(rows) >= 2:
            first, last = rows[0]["value"], rows[-1]["value"]
            delta = last - first
            trend = f"，期间 {'上升' if delta > 0 else '下降' if delta < 0 else '持平'} {abs(delta):g}{unit}"
        else:
            trend = ""
        lines.append(f"- {name}：最新 {latest['value']:g}{unit}（共 {len(rows)} 次）{trend}")

    return "\n".join(lines)


def call_llm(user_summary: str) -> str:
    if not AI_API_KEY:
        raise HTTPException(status_code=400, detail="未配置 AI 分析：请在环境变量中设置 AI_API_KEY")
    try:
        resp = requests.post(
            f"{AI_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_summary},
                ],
                "temperature": 0.6,
            },
            timeout=90,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return content.strip()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI 接口调用失败：{exc}") from exc


def generate_analysis(db, user_id: int, days: int) -> dict:
    today = today_date()
    start = today - timedelta(days=days - 1)
    summary = build_summary(db, user_id, days)
    content = call_llm(summary)
    cursor = db.execute(
        "INSERT INTO analyses (user_id, period_start, period_end, content, model, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), content, AI_MODEL, utc_now_str()),
    )
    row = db.execute("SELECT * FROM analyses WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _serialize(row)


def _serialize(row) -> dict:
    return {
        "id": row["id"],
        "period_start": row["period_start"],
        "period_end": row["period_end"],
        "content": row["content"],
        "model": row["model"],
        "created_at": row["created_at"],
    }
