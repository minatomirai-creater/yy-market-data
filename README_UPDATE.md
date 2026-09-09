# YY JPX Universe Auto Refresh Update

このパッケージは `yy-market-data` リポジトリを以下の構成へ更新します。

## 追加 / 更新ファイル

- `scripts/refresh_jpx_universe.py`
- `requirements.txt`
- `.github/workflows/yy-yfinance-weekly.yml`

## 動作

1. JPX公式「東証上場銘柄一覧」ページから最新Excelリンクを自動検出
2. Prime / Standard / Growth のみ抽出
3. ETF / ETN / REIT / 投資法人 / インフラファンド等を除外
4. 4文字コードを `input.lst` へ出力
5. 前回件数との乖離が5%超なら停止
6. 最新 `input.lst` を8 shardへ配布
7. yfinance取得
8. merge後に以下をGitHubへcommit
   - `input.lst`
   - `data/universe/jpx_universe_latest.csv`
   - `data/latest/yy_market_data_latest.csv`
   - `data/latest/yy_market_data_latest.meta.json`

## GitHubへの配置

ZIPを展開後、各ファイルをリポジトリの同じ相対パスへ上書きしてください。

特に `.github/workflows/yy-yfinance-weekly.yml` は必ずリポジトリ直下の `.github/workflows/` に置いてください。

## 実行時刻

毎週金曜 23:30 JST に自動開始します。YY Weekly IC は土曜 08:00 JST のため、約8.5時間の余裕があります。

## 最初の確認

GitHub Actionsから `YY yfinance weekly collection` を手動実行し、次のジョブが順番に成功することを確認してください。

- Refresh JPX universe
- Collect shard 0 ... 7
- Merge and publish latest

成功後、Codeタブに以下が生成されます。

- `data/universe/jpx_universe_latest.csv`
- `data/latest/yy_market_data_latest.csv`
- `data/latest/yy_market_data_latest.meta.json`

また `input.lst` 自体も最新JPX universeへ更新されます。
