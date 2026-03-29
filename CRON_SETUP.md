# SeaCurrent `.nc` 下載 + 轉換排程（每 2 天）

目標：每隔 2 天自動下載 SeaCurrent 相關 NetCDF (`.nc`) 並轉成漂流預測可直接使用的格式。

## 1) 手動測試

在專案根目錄執行下載：

```bash
python3 scripts/download_seacurrent_nc.py --output data/nc_files
```

執行轉換（把 `UC/VC` 改為 OpenDrift 常用欄位）：

```bash
python3 scripts/convert_seacurrent_for_drift.py --input-dir data/nc_files --output-dir data/nc_converted
```

## 2) 設定 cron（每 2 天）

```bash
crontab -e
```

加入以下內容（UTC 02:00，每 2 天執行一次；下載後立刻做轉換）：

```cron
0 2 */2 * * /bin/bash /workspace/seacurrent/scripts/run_download_seacurrent.sh
```

## 3) 只排轉換（可選）

如果你已經有別的下載來源，只想排「轉換」也可加：

```cron
30 2 */2 * * cd /workspace/seacurrent && /usr/bin/python3 scripts/convert_seacurrent_for_drift.py --input-dir data/nc_files --output-dir data/nc_converted >> logs/convert_seacurrent.log 2>&1
```

## 4) 檢查排程結果

```bash
tail -n 100 logs/download_and_convert_seacurrent.log
```

轉換後檔案位置：

- `data/nc_converted/`

下載原始檔與清單位置：

- `data/nc_files/`
- `data/nc_files/manifest.json`

## 5) 與漂流預測銜接

後續可直接使用轉換後的流場檔案（`x_sea_water_velocity` / `y_sea_water_velocity`）進入落水漂流模擬。
