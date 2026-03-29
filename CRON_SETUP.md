# SeaCurrent `.nc` 自動下載（每 2 天）

目標：每隔 2 天自動下載 SeaCurrent 相關的 NetCDF (`.nc`) 檔案，作為後續「人員落水漂流預測」資料來源。

## 0) 建立預測環境（requirements）

建議先建立虛擬環境，再安裝預測與下載所需套件：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 1) 手動先測試一次

在專案根目錄執行：

```bash
python3 scripts/download_seacurrent_nc.py --output data/nc_files
```

若想抓取 `Model/` 底下所有 `.nc`（不只關鍵字過濾）：

```bash
python3 scripts/download_seacurrent_nc.py --output data/nc_files --all-nc
```

## 2) 設定 cron（每 2 天）

```bash
crontab -e
```

加入以下內容（UTC 02:00，每 2 天執行一次）：

```cron
0 2 */2 * * /bin/bash /workspace/seacurrent/scripts/run_download_seacurrent.sh
```

> 如果你想用台灣時間（UTC+8）凌晨 2 點，可以改成 UTC 前一天 18:00：
>
> ```cron
> 0 18 */2 * * /bin/bash /workspace/seacurrent/scripts/run_download_seacurrent.sh
> ```

## 3) 檢查是否有成功執行

```bash
tail -n 100 logs/download_seacurrent.log
```

下載檔案會放在：

- `data/nc_files/`
- `data/nc_files/manifest.json`（紀錄下載清單）

## 4) 與漂流預測流程銜接（建議）

你可以把預測主程式也放進 cron，在下載成功後接著跑：

```bash
python3 your_drift_forecast.py --current data/nc_files/M-B0071-000.nc
```

建議在預測程式內檢查：

1. `manifest.json` 是否存在。
2. `.nc` 檔案時間戳是否為最近一次更新。
3. 若無新資料則沿用前次資料並發出警示（避免流程中斷）。
