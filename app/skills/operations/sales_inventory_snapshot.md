---
name: sales_inventory_snapshot
description: 组合查询销售指标与库存排行，输出一段经营概览和库存观察。
---

# 目标
当用户希望一次看到销售表现和库存情况时，先确定指标口径和时间范围，再依次调用 `data_center_query_metric` 与 `data_center_top_products`，最后输出一段经营概览。

# 适用问题
- 给我看下本月销售额和库存最高的前 5 个商品
- 看一下上个月订单量，再列出库存最高的前 3 个 SKU
- 帮我做一个销售和库存的简报

# 执行要求
1. 这个 skill 至少要调用两个 MCP tool：
   - 先调用 `data_center_query_metric`
   - 再调用 `data_center_top_products`
2. 指标映射规则：
   - 销售额、营收、GMV 优先映射为 `sales_amount`
   - 订单量映射为 `order_count`
   - 客单价映射为 `avg_order_value`
   - 如果用户没有明确指标，默认按 `sales_amount`
3. 时间范围规则：
   - 如果用户使用 `本月`、`上个月`、`近30天`、`今日` 这类相对时间口径，必须先调用 `get_time`
   - `time_range_label` 使用用户原始口径；如果用户没写，默认按 `本月`
4. 库存排行规则：
   - 默认 `scope=全部商品`
   - 默认 `rank_by=stock`
   - 默认 `top_k=5`
   - 如果用户指定“前 N 个”，把 `top_k` 设置为对应数字
   - 如果用户指定仓库，把 `warehouse` 传给 `data_center_top_products`
5. 如果用户只问单一指标或只问库存排行，不要优先使用这个 skill，优先使用更专门的 skill

# 输出要求
- 先给一句总览结论
- 分成“销售指标”和“库存排行”两个部分
- 销售部分明确指标口径、统计区间和数值
- 库存部分列出前几名商品，尽量包含 SKU、库存、可售库存和仓库
- 最后补一句简短观察，例如是否存在库存集中或库存压力
- 明确当前数据来自 mock 服务
