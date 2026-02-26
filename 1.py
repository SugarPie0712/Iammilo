from flask import Flask, request, render_template_string

app = Flask(__name__)

# ================== 作物适宜 pH 范围（由图片整理，近似值，可自行调整） ==================
# 统一使用简体中文作键名，并增加部分繁体→简体别名
CROP_PH_RANGES = {
    # 第一张图（主要是蔬菜+部分作物）——数值按 4.5~7.5 刻度近似
    "凤梨": (4.5, 6.0),
    "菠萝": (4.5, 6.0),   # 别名
    "茶": (4.5, 5.5),
    "水稻": (5.0, 6.5),
    "草莓": (5.0, 6.5),
    "黄瓜": (5.5, 7.5),
    "甘蔗": (5.5, 7.5),
    "葡萄": (6.0, 7.5),
    "豆类": (6.0, 7.5),
    "大豆": (6.0, 7.5),
    "花生": (5.5, 7.0),
    "辣椒": (5.5, 7.0),
    "南瓜": (5.5, 7.5),
    "玉米": (5.5, 7.5),
    "小麦": (6.0, 7.5),
    "番茄": (5.5, 7.5),

    # 第二张图（主要是果树等）——同样是近似范围
    "柑橘": (5.0, 7.5),
    "橙子": (5.0, 7.5),
    "桔子": (5.0, 7.5),
    "葡萄": (5.5, 7.5),
    "木瓜": (5.5, 7.5),
    "柠檬": (5.5, 7.5),
    "枇杷": (5.5, 7.5),
    "梨": (6.0, 7.5),
    "苹果": (5.5, 7.5),
    "香蕉": (5.0, 7.0),
    "芹菜": (6.0, 7.5),
    "椰子": (5.5, 7.5),
    "甘蓝": (6.0, 7.5),
    "卷心菜": (6.0, 7.5),
    "莴苣": (6.0, 7.5),
    "生菜": (6.0, 7.5),
    "菠菜": (6.0, 7.5),
    "豌豆": (6.0, 7.5),
    "洋葱": (6.0, 7.5),
    "白菜": (6.0, 7.5),
}

# 常见繁体→简体映射（输入时会自动转换）
TRAD_TO_SIMPLIFIED = {
    "鳳梨": "凤梨",
    "茶樹": "茶",
    "葡萄": "葡萄",  # 同形
    "蘋果": "苹果",
    "檸檬": "柠檬",
    "枇杷": "枇杷",
    "香蕉": "香蕉",  # 同形
    "甘藍": "甘蓝",
    "蕃茄": "番茄",
    "蔥": "葱",
    "蔬菜": "蔬菜",  # 示例
    "洋蔥": "洋葱",
    "白菜": "白菜",
}


def normalize_crop_name(name: str) -> str:
    """把作物名去空格、转简体（只做简单字符/词级替换）。"""
    name = name.strip()
    if not name:
        return ""

    # 先做整词替换
    if name in TRAD_TO_SIMPLIFIED:
        return TRAD_TO_SIMPLIFIED[name]

    # 再做按字符替换（非常粗略，仅覆盖常见）
    char_map = {
        "鳳": "凤",
        "檸": "柠",
        "蘋": "苹",
        "藍": "蓝",
        "蔥": "葱",
        "蔬": "蔬",
        "蔣": "蒋",  # 示例
    }
    name = "".join(char_map.get(ch, ch) for ch in name)
    return name


# ================== 土壤酸碱性推理 ==================
def infer_soil_type_from_features(form_data):
    """
    根据 1–6 点土壤特征打分，返回 ("酸性" / "中性" / "碱性", 解释文本)
    规则：每个问题如果选择“偏酸性特征”则 acid_score+1，选择“偏碱性特征”则 alkaline_score+1。
    """
    acid_score = 0
    alkaline_score = 0
    reasons = []

    # 1. 土源
    src = form_data.get("source", "")
    if src == "forest":
        acid_score += 1
        reasons.append("土源来自山林/腐殖质土，一般偏酸性。")
    elif src == "plain":
        alkaline_score += 1
        reasons.append("土源来自平原/盐碱地，一般偏碱性。")

    # 2. 地表植物
    plants = form_data.get("surface_plants", "")
    if plants == "pine_rhododendron":
        acid_score += 1
        reasons.append("地表多松树、杜鹃等喜酸植物，说明土壤偏酸性。")
    elif plants == "millet_sorghum":
        alkaline_score += 1
        reasons.append("地表多谷子、高粱等耐碱植物，说明土壤偏碱性。")

    # 3. 颜色
    color = form_data.get("color", "")
    if color == "dark":
        acid_score += 1
        reasons.append("土壤颜色较深（黑褐色），一般为酸性土。")
    elif color == "light":
        alkaline_score += 1
        reasons.append("土壤颜色浅且表面有白色盐碱，一般为碱性土。")

    # 4. 手感
    touch = form_data.get("touch", "")
    if touch == "soft_loose":
        acid_score += 1
        reasons.append("手感疏松、容易散开，一般为酸性土。")
    elif touch == "hard_clod":
        alkaline_score += 1
        reasons.append("手感坚硬、易结块，一般为碱性土。")

    # 5. 浇水状态
    water = form_data.get("water_state", "")
    if water == "fast_no_foam":
        acid_score += 1
        reasons.append("浇水下渗快、不冒白泡，通常为酸性土。")
    elif water == "slow_with_foam":
        alkaline_score += 1
        reasons.append("浇水下渗慢，表面冒白泡/有白色物质，通常为碱性土。")

    # 6. 质地
    texture = form_data.get("texture", "")
    if texture == "loose":
        acid_score += 1
        reasons.append("质地疏松、透水透气好，一般偏酸性。")
    elif texture == "compact":
        alkaline_score += 1
        reasons.append("质地坚硬、易板结，一般偏碱性。")

    # 依据得分判断
    if acid_score > alkaline_score:
        soil_type = "酸性"
    elif alkaline_score > acid_score:
        soil_type = "碱性"
    else:
        soil_type = "中性或难以判断"

    explanation = "；".join(reasons) if reasons else "未选择足够的特征，难以判断。"
    explanation += f"（酸性评分：{acid_score}，碱性评分：{alkaline_score}）"
    return soil_type, explanation


def estimate_ph_from_type(soil_type: str) -> float:
    """在用户没有输入 pH 时，根据酸/碱性给一个典型估计值，仅用于大致参考。"""
    if soil_type == "酸性":
        return 5.5
    if soil_type == "碱性":
        return 8.0
    return 7.0


# ================== 页面模板 ==================
INDEX_HTML = """
<!doctype html>
<html lang="zh-cn">
<head>
  <meta charset="utf-8">
  <title>土壤酸碱度与作物适宜性小工具</title>
  <style>
    body { font-family: Arial, "微软雅黑", sans-serif; max-width: 960px; margin: 20px auto; background:#f7f7fb; }
    h1 { text-align:center; color:#2c3e50; }
    fieldset { border:1px solid #ddd; padding:15px 20px; margin-bottom:20px; background:#fff; border-radius:8px; }
    legend { font-weight:bold; }
    label { display:block; margin:4px 0; }
    .section-title { margin-top:10px; font-weight:bold; }
    .submit-btn { padding:10px 20px; font-size:16px; background:#27ae60; color:#fff; border:none; border-radius:6px; cursor:pointer; }
    .submit-btn:hover { background:#1e874b; }
    .hint { color:#777; font-size:13px; }
  </style>
</head>
<body>
  <h1>土壤酸碱度与作物适宜性查询</h1>
  <form method="post" action="/result">
    <fieldset>
      <legend>一、土壤观测信息</legend>

      <div class="section-title">1. 土源（土壤来自哪里？）</div>
      <label><input type="radio" name="source" value="forest"> 山林、沟壑腐殖土（黑色或褐色、疏松）</label>
      <label><input type="radio" name="source" value="plain"> 平原、盐碱地等（颜色较浅，可能有白色结晶）</label>
      <label><input type="radio" name="source" value="" checked> 不确定 / 不使用该项</label>

      <div class="section-title">2. 地表植物（原来长什么植物？）</div>
      <label><input type="radio" name="surface_plants" value="pine_rhododendron"> 松树、杉树、杜鹃等</label>
      <label><input type="radio" name="surface_plants" value="millet_sorghum"> 谷子、高粱、卤蓬等</label>
      <label><input type="radio" name="surface_plants" value="" checked> 不确定 / 不使用该项</label>

      <div class="section-title">3. 土壤颜色</div>
      <label><input type="radio" name="color" value="dark"> 黑色、黑褐色等较深颜色</label>
      <label><input type="radio" name="color" value="light"> 偏白、偏黄、表面常有一层白色盐碱</label>
      <label><input type="radio" name="color" value="" checked> 不确定 / 不使用该项</label>

      <div class="section-title">4. 用手抓一把土的感觉</div>
      <label><input type="radio" name="touch" value="soft_loose"> 软软的，捏紧后一松手就散开</label>
      <label><input type="radio" name="touch" value="hard_clod"> 挺硬实，松手后容易结块不散开</label>
      <label><input type="radio" name="touch" value="" checked> 不确定 / 不使用该项</label>

      <div class="section-title">5. 浇水后的状态</div>
      <label><input type="radio" name="water_state" value="fast_no_foam"> 下渗快，不冒白泡，水面较浑</label>
      <label><input type="radio" name="water_state" value="slow_with_foam"> 下渗慢，水面冒白泡/有白沫，有时表面有白色物质</label>
      <label><input type="radio" name="water_state" value="" checked> 不确定 / 不使用该项</label>

      <div class="section-title">6. 土壤质地</div>
      <label><input type="radio" name="texture" value="loose"> 疏松，透气透水性强</label>
      <label><input type="radio" name="texture" value="compact"> 质地坚硬，容易板结成块</label>
      <label><input type="radio" name="texture" value="" checked> 不确定 / 不使用该项</label>

      <div class="section-title">7. pH 试纸测得的数值（可选）</div>
      <input type="number" step="0.1" name="ph_value" placeholder="例如 6.2" min="3.0" max="10.0">
      <span class="hint">如不填写，将根据以上特征估计一个典型 pH 值，仅供参考。</span>
    </fieldset>

    <fieldset>
      <legend>二、计划种植的作物</legend>
      <label>请输入作物名称（多个作物用逗号分隔，如：番茄, 辣椒, 甘蓝）</label>
      <textarea name="crops" rows="3" style="width:100%;"></textarea>
      <p class="hint">
        支持常见的繁体/简体名称（例如：蕃茄 → 番茄，鳳梨 → 凤梨）。<br>
        目前内置了：凤梨/菠萝、茶、水稻、草莓、黄瓜、甘蔗、葡萄、豆类/大豆、花生、辣椒、南瓜、玉米、小麦、番茄、柑橘、木瓜、柠檬、枇杷、梨、苹果、香蕉、芹菜、椰子、甘蓝/卷心菜、莴苣/生菜、菠菜、豌豆、洋葱、白菜 等。
      </p>
    </fieldset>

    <div style="text-align:center; margin-bottom:40px;">
      <button type="submit" class="submit-btn">提交并查看结果</button>
    </div>
  </form>
</body>
</html>
"""

RESULT_HTML = """
<!doctype html>
<html lang="zh-cn">
<head>
  <meta charset="utf-8">
  <title>评估结果</title>
  <style>
    body { font-family: Arial, "微软雅黑", sans-serif; max-width: 960px; margin: 20px auto; background:#f7f7fb; }
    h1 { text-align:center; color:#2c3e50; }
    .box { background:#fff; border-radius:8px; padding:15px 20px; margin-bottom:20px; border:1px solid #ddd; }
    .tag { display:inline-block; padding:2px 8px; border-radius:10px; font-size:12px; margin-left:5px; }
    .tag-acid { background:#e74c3c; color:#fff; }
    .tag-alk { background:#2980b9; color:#fff; }
    .tag-neutral { background:#95a5a6; color:#fff; }
    table { width:100%; border-collapse:collapse; margin-top:10px; }
    th, td { border:1px solid #ddd; padding:6px 8px; text-align:center; }
    th { background:#f0f0f5; }
    .ok { color:#27ae60; font-weight:bold; }
    .bad { color:#c0392b; font-weight:bold; }
    .hint { color:#777; font-size:13px; }
    a { color:#2980b9; text-decoration:none; }
  </style>
</head>
<body>
  <h1>评估结果</h1>

  <div class="box">
    <h2>土壤酸碱性判断
      {% if soil_type == "酸性" %}
        <span class="tag tag-acid">酸性</span>
      {% elif soil_type == "碱性" %}
        <span class="tag tag-alk">碱性</span>
      {% else %}
        <span class="tag tag-neutral">中性 / 难以判断</span>
      {% endif %}
    </h2>
    <p>{{ explanation }}</p>
    <p>用于匹配作物的 pH 值：<strong>{{ used_ph }}</strong>
      {% if ph_from_user %}
        （来源：你输入的 pH 试纸数值）
      {% else %}
        （根据酸/碱性推测的典型值，仅供参考）
      {% endif %}
    </p>
  </div>

  <div class="box">
    <h2>作物适宜性</h2>
    {% if crop_results %}
      <table>
        <tr>
          <th>作物名称</th>
          <th>适宜 pH 范围</th>
          <th>是否在范围内</th>
          <th>说明</th>
        </tr>
        {% for r in crop_results %}
        <tr>
          <td>{{ r.name }}</td>
          <td>
            {% if r.range_min is not none %}
              {{ r.range_min }} ~ {{ r.range_max }}
            {% else %}
              未收录
            {% endif %}
          </td>
          <td>
            {% if r.range_min is none %}
              <span class="hint">未知</span>
            {% elif r.suitable %}
              <span class="ok">适宜</span>
            {% else %}
              <span class="bad">不太适宜</span>
            {% endif %}
          </td>
          <td>{{ r.message }}</td>
        </tr>
        {% endfor %}
      </table>
    {% else %}
      <p>没有检测到有效的作物名称，请返回重新输入。</p>
    {% endif %}
    <p class="hint">说明：作物适宜 pH 范围根据你提供的图表整理，数值为估算值，仅供种植参考，实际还需结合当地气候、品种和管理水平。</p>
  </div>

  <p style="text-align:center;">
    <a href="/">返回继续评估</a>
  </p>
</body>
</html>
"""


# ================== 路由 ==================
@app.route("/", methods=["GET"])
def index():
    return render_template_string(INDEX_HTML)


@app.route("/result", methods=["POST"])
def result():
    form = request.form

    # 1. 先根据特征判断酸/碱性
    soil_type, explanation = infer_soil_type_from_features(form)

    # 2. 获取用户 pH（如果有的话）
    ph_raw = form.get("ph_value", "").strip()
    ph_value = None
    ph_from_user = False
    if ph_raw:
        try:
            ph_value = float(ph_raw)
            ph_from_user = True
        except ValueError:
            ph_value = None

    if ph_value is None:
        ph_value = estimate_ph_from_type(soil_type)

    # 3. 解析作物列表
    crops_raw = form.get("crops", "")
    # 支持中文逗号、英文逗号、顿号分隔
    for ch in ["，", "、", ";", "；"]:
        crops_raw = crops_raw.replace(ch, ",")
    crop_names = [normalize_crop_name(n) for n in crops_raw.split(",")]
    crop_names = [n for n in crop_names if n]

    crop_results = []
    for name in crop_names:
        if name in CROP_PH_RANGES:
            min_ph, max_ph = CROP_PH_RANGES[name]
            suitable = (min_ph <= ph_value <= max_ph)
            if suitable:
                msg = f"当前 pH≈{ph_value:.1f}，在 {name} 的适宜范围内，可以考虑种植。"
            else:
                if ph_value < min_ph:
                    trend = "偏酸"
                elif ph_value > max_ph:
                    trend = "偏碱"
                else:
                    trend = "偏离适宜范围"
                msg = f"当前 pH≈{ph_value:.1f}，{trend}，不在 {name} 的最佳范围内，如要种植建议先改良土壤。"
            crop_results.append({
                "name": name,
                "range_min": min_ph,
                "range_max": max_ph,
                "suitable": suitable,
                "message": msg
            })
        else:
            crop_results.append({
                "name": name,
                "range_min": None,
                "range_max": None,
                "suitable": False,
                "message": "暂未收录该作物的 pH 适宜范围，可手动补充到程序中的字典。"
            })

    return render_template_string(
        RESULT_HTML,
        soil_type=soil_type,
        explanation=explanation,
        used_ph=f"{ph_value:.1f}",
        ph_from_user=ph_from_user,
        crop_results=crop_results
    )


if __name__ == "__main__":
    # 开发环境运行
    app.run(host="0.0.0.0", port=5000, debug=True)