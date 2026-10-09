# A股V1.2 技术扫描器（独立试运行版）

本扫描器是**新闻早报以外的独立工作流**：不改动 `crawler.yml`，不覆盖 TrendRadar 的原文件，**不自动买卖或推送**。

## GitHub Actions

- 手动：仓库 Actions → **A股 V1.2 技术扫描** → Run workflow；第一次选 `scan_date=2026-10-09`、`limit=100` 验证接口。
- 全量：验证通过后，在 Actions 手动运行时设 `limit=0`。
- 定时：北京时间周一至周五 **17:37** 自动尝试全市场扫描，可能延迟或受行情接口限流影响。
- 结果：进入运行记录 → **Artifacts** → 下载 `a-share-v12-...`，包含全部技术结果、提前预警池、强势候选、数据缺口、需核查定增清单和结果说明。
- 节假日：若自动任务命中非交易日可能失败并记录原因，不会把旧行情当成新行情。

## 重要风险：只是技术预筛

1. 使用 BaoStock 历史前复权日K，能核算10项技术条件（BBI、ADX、MFI、Donchian、DI、OBV、ATR）。**另2项VPVR无法凭日K精确复现**，必须另行核查价格成交分布。
2. **定增一票否决**：候选必须逐只核对交易所或巨潮资讯公司公告，进行中定增、近期相关限售风险、公告核查不明，均不列为可买入推荐。空白 `placement_review.csv` 表示**全部待核实**，不能擅自填写“通过”。
3. 预警池和确认池只是待研究名单，**所有输出的“可直接买入”均为 False**。技术阈值尚未经过全市场样本外回测。
4. 非科创板/北交所/当前ST标的排除，创业板保留；上市不足150有效交易日的股票进入数据缺口。
5. 首次100股只是功能检测，不代表全市场；全量需要检查计算成功数量、采集日期、失败数和缺失情况。
6. BaoStock 公共服务可能超时/不可用；该程序还没有在 GitHub Actions 在线验证，也未做真实全市场性能测试。

## 本地运行

```bash
python -m pip install -r scanner_v12/requirements.txt
python -m unittest discover -s scanner_v12/tests -v
python scanner_v12/scan.py --date 2026-10-09 --limit 100
python scanner_v12/scan.py --date 2026-10-09 --limit 0
```

报告保存在 `scanner_v12/output/`。获取新买点前，应复核题材预期差、公司公告、竞价和T+1风险。
