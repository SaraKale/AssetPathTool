# -*- coding: utf-8 -*-
"""多语言。

做法：界面上所有静态文案一律用「中文原文」创建，建完再整体翻译一遍。
  · 中文原文同时充当 key，缺翻译时原样返回，永远不会出现空白界面；
  · 切语言时只改控件文案，不重建窗口，所以输入框里的路径、表格里的数据都还在；
  · 表格内容 / 状态栏这类动态文字用 tr("模板 {}").format(...) 现算，切完重绘一次即可。

新增语言只要：① 往 LANGS 加一行；② 给 _T 的每条补一列。
"""
import json
import os
import sys

from .appinfo import config_path, legacy_config_path

# ---------------------------------------------------------------- 语言清单
# (内部代码, 下拉框里显示的名字)。显示名用各语言的自称，不翻译。
LANGS = [
    ("zh-CN", "简体中文"),
    ("zh-TW", "繁體中文"),
    ("en", "English"),
    ("ja", "日本語"),
]
CODES = [c for c, _ in LANGS]
NAMES = dict(LANGS)

# 当前语言（模块级；用 set_current() 改，tr() 每次调用时读）
LANG = "zh-CN"

# key = 中文原文（带 {} 占位符的是 format 模板）
# value = (繁體中文, English, 日本語)
_T = {
    # ---- 框架 ----
    "素材路径提取工具": ("素材路徑提取工具", "Asset Path Tool", "素材パス抽出ツール"),
    "提取 · 对比 · 重定向 · 使用统计　Premiere Pro / After Effects / Audition 项目素材路径":
        ("擷取 · 比對 · 重定向 · 使用統計　Premiere Pro / After Effects / Audition 專案素材路徑",
         "Extract · Compare · Remap · Usage — asset paths in "
         "Premiere Pro / After Effects / Audition projects",
         "抽出 · 比較 · 再指定 · 使用状況　Premiere Pro / After Effects / Audition の素材パス"),
    "  ① 提取路径  ": ("  ① 擷取路徑  ", "  ① Extract  ", "  ① パス抽出  "),
    "  ② 对比项目  ": ("  ② 比對專案  ", "  ② Compare  ", "  ② 比較  "),
    "  ③ 路径重定向  ": ("  ③ 路徑重定向  ", "  ③ Remap  ", "  ③ パス再指定  "),
    "  ④ 素材使用  ": ("  ④ 素材使用  ", "  ④ Usage  ", "  ④ 使用状況  "),
    "语言": ("語言", "Language", "言語"),

    # ---- 通用 ----
    "就绪": ("就緒", "Ready", "準備完了"),
    "浏览…": ("瀏覽…", "Browse…", "参照…"),
    "项目文件": ("專案檔", "Project file", "プロジェクト"),
    "选择项目文件": ("選擇專案檔", "Select project file", "プロジェクトを選択"),
    "项目 / XML / AE / AU 工程":
        ("專案 / XML / AE / AU 工程", "Project / XML / AE / AU", "プロジェクト / XML / AE / AU"),
    "Premiere 项目": ("Premiere 專案", "Premiere project", "Premiere プロジェクト"),
    "After Effects 工程": ("After Effects 工程", "After Effects project", "After Effects プロジェクト"),
    "Audition 会话": ("Audition 工作階段", "Audition session", "Audition セッション"),
    "XML 文件": ("XML 檔案", "XML file", "XML ファイル"),
    "所有文件": ("所有檔案", "All files", "すべてのファイル"),
    "文本文件": ("文字檔", "Text file", "テキストファイル"),
    "CSV 文件": ("CSV 檔案", "CSV file", "CSV ファイル"),
    "全部": ("全部", "All", "すべて"),
    "只看": ("只看", "Show", "表示"),
    "筛选": ("篩選", "Filter", "絞り込み"),
    "名称": ("名稱", "Name", "名前"),
    "状态": ("狀態", "Status", "状態"),
    "无路径": ("無路徑", "No path", "パスなし"),
    "正常": ("正常", "OK", "正常"),
    "缺失": ("缺失", "Missing", "欠落"),
    "存在": ("存在", "Found", "存在"),
    "（未分类）": ("（未分類）", "(Uncategorized)", "（未分類）"),
    "(根目录)": ("(根目錄)", "(root)", "(ルート)"),
    "(无源文件)": ("(無來源檔)", "(no source file)", "(ソースなし)"),
    "已导出：{}": ("已匯出：{}", "Exported: {}", "書き出しました：{}"),
    "已导出：\n{}": ("已匯出：\n{}", "Exported:\n{}", "書き出しました：\n{}"),
    "操作失败": ("操作失敗", "Operation failed", "操作に失敗しました"),
    "{} 项": ("{} 項", "{} items", "{} 件"),

    # ---- 页面① 提取 ----
    "把 .prproj / .aep / .sesx 拖到这里，或点「浏览…」":
        ("把 .prproj / .aep / .sesx 拖到這裡，或點「瀏覽…」",
         "Drop a .prproj / .aep / .sesx here, or click Browse…",
         ".prproj / .aep / .sesx をここにドロップ、または「参照…」"),
    "开始提取": ("開始擷取", "Extract", "抽出開始"),
    "只看缺失素材": ("只看缺失素材", "Missing only", "欠落のみ"),
    "导出 TXT": ("匯出 TXT", "Export TXT", "TXT 出力"),
    "导出 CSV": ("匯出 CSV", "Export CSV", "CSV 出力"),
    "素材条目": ("素材項目", "Assets", "素材数"),
    "有路径": ("有路徑", "With path", "パスあり"),
    "硬盘缺失": ("硬碟缺失", "Missing", "欠落"),
    "文件夹": ("資料夾", "Folders", "フォルダ"),
    "▾  展开全部": ("▾  展開全部", "▾  Expand all", "▾  すべて展開"),
    "▸  收起全部": ("▸  收合全部", "▸  Collapse all", "▸  すべて折りたたむ"),
    "硬盘路径": ("硬碟路徑", "Path on disk", "ディスクパス"),
    "项目文件夹 / 素材名": ("專案資料夾 / 素材名", "Project folder / Asset", "プロジェクトフォルダ / 素材名"),
    "选择项目文件后点「开始提取」\n\n支持 .prproj（无需手动解压）、.aep（After Effects）、.sesx（Audition）和已解压的 .xml":
        ("選擇專案檔後點「開始擷取」\n\n支援 .prproj（無需手動解壓）、.aep（After Effects）、.sesx（Audition）與已解壓的 .xml",
         "Pick a project file, then click Extract\n\nSupports .prproj (no unzip needed), "
         ".aep (After Effects), .sesx (Audition) and plain .xml",
         "プロジェクトを選んで「抽出開始」を押してください\n\n.prproj（解凍不要）、"
         ".aep（After Effects）、.sesx（Audition）、展開済み .xml に対応"),
    "请先选择一个存在的项目文件（.prproj / .aep / .sesx / .xml）":
        ("請先選擇一個存在的專案檔（.prproj / .aep / .sesx / .xml）",
         "Please choose an existing project file (.prproj / .aep / .sesx / .xml)",
         "存在するプロジェクト（.prproj / .aep / .sesx / .xml）を選んでください"),
    "正在解析项目，大项目需要十几秒…":
        ("正在解析專案，大專案需要十幾秒…",
         "Parsing project — large ones take a while…",
         "プロジェクトを解析中…大きなものは少し時間がかかります"),
    "没有符合条件的素材": ("沒有符合條件的素材", "No assets match the filter", "条件に合う素材がありません"),
    "这个工程里没找到素材路径":
        ("這個工程裡沒找到素材路徑",
         "No asset paths found in this project",
         "このプロジェクトに素材パスが見つかりません"),
    "没有从这个工程里找到素材路径。\n\n"
    "可能的原因：\n"
    "· 工程里没有引用任何外部素材\n"
    "· 文件格式不是本工具支持的（.prproj / .aep / .sesx / .xml）\n"
    "· 文件损坏或被加密":
        ("沒有從這個工程裡找到素材路徑。\n\n"
         "可能的原因：\n"
         "· 工程裡沒有引用任何外部素材\n"
         "· 檔案格式不是本工具支援的（.prproj / .aep / .sesx / .xml）\n"
         "· 檔案損壞或被加密",
         "No asset paths were found in this project.\n\n"
         "Likely reasons:\n"
         "· the project references no external media\n"
         "· the format is not supported (.prproj / .aep / .sesx / .xml)\n"
         "· the file is damaged or encrypted",
         "このプロジェクトから素材パスが見つかりませんでした。\n\n"
         "考えられる原因：\n"
         "· 外部素材を参照していない\n"
         "· 対応していない形式（.prproj / .aep / .sesx / .xml）\n"
         "· ファイルが破損、または暗号化されている"),
    "提取完成：共 {} 条素材，当前显示 {} 行":
        ("擷取完成：共 {} 條素材，目前顯示 {} 行",
         "Done: {} assets, {} rows shown",
         "完了：素材 {} 件、{} 行を表示中"),
    "已展开 {} 个文件夹": ("已展開 {} 個資料夾", "Expanded {} folders", "{} 個のフォルダを展開しました"),
    "已收起 {} 个文件夹": ("已收合 {} 個資料夾", "Collapsed {} folders", "{} 個のフォルダを折りたたみました"),
    "保存为 TXT": ("另存為 TXT", "Save as TXT", "TXT として保存"),
    "保存为 CSV": ("另存為 CSV", "Save as CSV", "CSV として保存"),
    "正在解析项目…": ("正在解析專案…", "Parsing project…", "プロジェクトを解析中…"),

    # ---- 页面② 对比 ----
    "A（旧）": ("A（舊）", "A (old)", "A（旧）"),
    "B（新）": ("B（新）", "B (new)", "B（新）"),
    "拖入旧版本 .prproj / .aep，或点「浏览…」":
        ("拖入舊版本 .prproj / .aep，或點「瀏覽…」",
         "Drop the old .prproj / .aep here, or click Browse…",
         "旧バージョンの .prproj / .aep をドロップ、または「参照…」"),
    "拖入新版本 .prproj / .aep，或点「浏览…」":
        ("拖入新版本 .prproj / .aep，或點「瀏覽…」",
         "Drop the new .prproj / .aep here, or click Browse…",
         "新バージョンの .prproj / .aep をドロップ、または「参照…」"),
    "开始对比": ("開始比對", "Compare", "比較開始"),
    "包含序列/调整图层等无源文件条目":
        ("包含序列/調整圖層等無來源檔條目", "Include items with no source file",
         "ソースのない項目（シーケンス等）も含める"),
    "导出报告": ("匯出報告", "Export report", "レポート出力"),
    "新增": ("新增", "Added", "追加"),
    "删除": ("刪除", "Removed", "削除"),
    "路径变化": ("路徑變化", "Path changed", "パス変更"),
    "位置变化": ("位置變化", "Moved", "場所変更"),
    "未变": ("未變", "Unchanged", "変更なし"),
    "变化": ("變化", "Change", "変化"),
    "项目文件夹": ("專案資料夾", "Project folder", "プロジェクトフォルダ"),
    "素材名": ("素材名", "Asset", "素材名"),
    "A（旧）路径": ("A（舊）路徑", "A (old) path", "A（旧）パス"),
    "B（新）路径": ("B（新）路徑", "B (new) path", "B（新）パス"),
    "选两个项目文件（A 旧 / B 新）后点「开始对比」\n\n建议用同一个项目不同时期的两个 .prproj，或项目与自动保存副本":
        ("選兩個專案檔（A 舊 / B 新）後點「開始比對」\n\n建議用同一個專案不同時期的兩個 .prproj，或專案與自動儲存副本",
         "Pick two project files (A old / B new), then click Compare\n\nTip: two snapshots of the same project, or a project and its autosave copy",
         "2 つのプロジェクト（A 旧 / B 新）を選んで「比較開始」\n\n同じプロジェクトの別時期のもの、または自動保存のコピーがおすすめです"),
    "请选择两个都存在项目文件（A 旧 / B 新）":
        ("請選擇兩個都存在專案檔（A 舊 / B 新）",
         "Please pick two project files that both exist (A old / B new)",
         "実在する 2 つのプロジェクト（A 旧 / B 新）を選んでください"),
    "读取 A…": ("讀取 A…", "Reading A…", "A を読み込み中…"),
    "读取 B…": ("讀取 B…", "Reading B…", "B を読み込み中…"),
    "对比中…": ("比對中…", "Comparing…", "比較中…"),
    "正在对比两个项目…": ("正在比對兩個專案…", "Comparing the two projects…", "2 つのプロジェクトを比較中…"),
    "没有符合条件的变化": ("沒有符合條件的變化", "No changes match the filter", "条件に合う変化がありません"),
    "对比完成：A={}，B={}，当前显示 {} 行":
        ("比對完成：A={}，B={}，目前顯示 {} 行",
         "Done: A={}, B={}, {} rows shown",
         "完了：A={}、B={}、{} 行を表示中"),
    "保存对比报告": ("另存比對報告", "Save comparison report", "比較レポートを保存"),
    "保存对比 CSV": ("另存比對 CSV", "Save comparison CSV", "比較 CSV を保存"),
    "拖入的不是项目文件，已忽略":
        ("拖入的不是專案檔，已忽略", "Dropped file is not a project file — ignored",
         "プロジェクトファイルではないため無視しました"),
    "已载入对比文件：A = {}，B = {}　点「开始对比」":
        ("已載入比對檔案：A = {}，B = {}　點「開始比對」",
         "Loaded: A = {}, B = {} — click Compare",
         "読み込み完了：A = {}、B = {}　「比較開始」を押してください"),
    "已载入：{}　点上方按钮开始":
        ("已載入：{}　點上方按鈕開始", "Loaded: {} — click the button above", "読み込み完了：{}　上のボタンで開始"),

    # ---- 页面③ 重定向 ----
    "重定向规则": ("重定向規則", "Remap rules", "再指定ルール"),
    "重定向规则表": ("重定向規則表", "Remap rules", "再指定ルール表"),
    "规则表…": ("規則表…", "Rules…", "ルール表…"),
    "关闭": ("關閉", "Close", "閉じる"),
    "上移": ("上移", "Move up", "上へ"),
    "下移": ("下移", "Move down", "下へ"),
    "勾选首列方框后，「查找缺失…」只处理勾选的行":
        ("勾選首列方框後，「尋找缺失…」只處理勾選的行",
         "Tick the first column to make Find missing… work on those rows only",
         "先頭列にチェックすると「欠落を検索…」はその行だけを対象にします"),
    "已勾选 {} 条素材": ("已勾選 {} 條素材", "{} assets ticked", "{} 件をチェックしました"),
    "已取消全部勾选": ("已取消全部勾選", "All ticks cleared", "すべてのチェックを外しました"),
    "从上到下匹配，命中第一条生效":
        ("從上到下比對，命中第一條生效", "Matched top-down; the first hit wins", "上から順に照合し、最初の一致が適用されます"),
    "拖入 .prproj，或点「浏览…」":
        ("拖入 .prproj，或點「瀏覽…」", "Drop a .prproj here, or click Browse…",
         ".prproj をドロップ、または「参照…」"),
    "拖入 .prproj / .aep / .sesx，或点「浏览…」":
        ("拖入 .prproj / .aep / .sesx，或點「瀏覽…」",
         "Drop a .prproj / .aep / .sesx here, or click Browse…",
         ".prproj / .aep / .sesx をドロップ、または「参照…」"),
    "原路径前缀": ("原路徑前綴", "Old path prefix", "元のパス接頭辞"),
    "新路径前缀": ("新路徑前綴", "New path prefix", "新しいパス接頭辞"),
    "+ 添加规则": ("+ 新增規則", "+ Add rule", "+ ルール追加"),
    "删除选中": ("刪除選取", "Delete selected", "選択を削除"),
    "清空": ("清空", "Clear", "クリア"),
    "原前缀": ("原前綴", "Old prefix", "元の接頭辞"),
    "新前缀": ("新前綴", "New prefix", "新しい接頭辞"),
    "还没有规则\n\n填好上面两项后点「+ 添加规则」":
        ("還沒有規則\n\n填好上面兩項後點「+ 新增規則」",
         "No rules yet\n\nFill in the two fields above, then click + Add rule",
         "ルールがありません\n\n上の 2 項目を入力して「+ ルール追加」を押してください"),
    "建议先在 PR 里验证清单无误再改写，改写前请备份项目。":
        ("建議先在 PR 裡驗證清單無誤再改寫，改寫前請備份專案。",
         "Verify the list in Premiere first, and back up the project before rewriting.",
         "PR でリストを確認してから書き換えてください。事前にバックアップを。"),
    "加载全部": ("載入全部", "Load all", "すべて読み込み"),
    "应用规则": ("套用規則", "Apply rules", "ルール適用"),
    "清空手动指定": ("清空手動指定", "Clear overrides", "手動指定をクリア"),
    "勾选": ("勾選", "Tick", "チェック"),
    "全选": ("全選", "All", "すべて選択"),
    "全不选": ("全不選", "None", "すべて解除"),
    "先在表格里选中要勾选的行（Ctrl / Shift 可多选）":
        ("先在表格裡選取要勾選的行（Ctrl / Shift 可多選）",
         "Select the rows to tick first (Ctrl / Shift for several)",
         "先にチェックする行を選択してください（Ctrl / Shift で複数選択）"),
    "已勾选 {} 条素材　「查找缺失…」只处理勾选的行":
        ("已勾選 {} 條素材　「尋找缺失…」只處理勾選的行",
         "{} assets ticked — Find missing… only handles ticked rows",
         "{} 件をチェック　「欠落を検索…」はチェックした行だけを対象にします"),
    "要清除 {} 条手动指定的新位置吗？\n\n"
    "清除后这些行会重新按规则计算（没有规则就回到原路径）。\n"
    "「勾选」和「只看」的筛选不受影响。":
        ("要清除 {} 條手動指定的新位置嗎？\n\n"
         "清除後這些行會重新按規則計算（沒有規則就回到原路徑）。\n"
         "「勾選」和「只看」的篩選不受影響。",
         "Clear the manual new location for {} assets?\n\n"
         "Those rows go back to being computed from the rules "
         "(or the original path if no rule matches).\n"
         "Ticks and the Show filter are not affected.",
         "手動指定した新しい場所を {} 件クリアしますか？\n\n"
         "クリアした行はルールから再計算されます（一致するルールがなければ元のパス）。\n"
         "チェックと「表示」の絞り込みには影響しません。"),
    "查找缺失…": ("尋找缺失…", "Find missing…", "欠落を検索…"),
    "导出清单": ("匯出清單", "Export list", "リスト出力"),
    "命中改写": ("命中改寫", "Rewritten", "書き換え"),
    "新路径存在": ("新路徑存在", "New path found", "新パスあり"),
    "新路径缺失": ("新路徑缺失", "New path missing", "新パスなし"),
    "已改写": ("已改寫", "Rewritten", "書き換え済み"),
    "双击任意一行 → 弹出文件浏览窗口，单独指定这条素材的新位置；右键可清除或定位。":
        ("雙擊任意一行 → 彈出檔案瀏覽視窗，單獨指定這條素材的新位置；右鍵可清除或定位。",
         "Double-click any row to pick a new location for that asset; right-click to clear or reveal.",
         "行をダブルクリックで新しい場所を指定。右クリックで解除／エクスプローラーで表示。"),
    "原路径": ("原路徑", "Old path", "元のパス"),
    "新路径": ("新路徑", "New path", "新しいパス"),
    "点「加载全部」先列出所有素材\n\n然后双击任意一行，选择该素材的新位置":
        ("點「載入全部」先列出所有素材\n\n然後雙擊任意一行，選擇該素材的新位置",
         "Click Load all to list every asset\n\nThen double-click a row to choose its new location",
         "「すべて読み込み」で素材を一覧表示\n\n行をダブルクリックして新しい場所を選択"),
    "选择新位置…": ("選擇新位置…", "Choose new location…", "新しい場所を選択…"),
    "采用这个建议": ("採用這個建議", "Use this suggestion", "この候補を採用"),
    "已为「{}」单独指定新位置":
        ("已為「{}」單獨指定新位置", "Set a new location for “{}”", "「{}」の新しい場所を指定しました"),
    "这个文件现在不存在，无法定位。":
        ("這個檔案目前不存在，無法定位。",
         "That file doesn't exist right now, so it can't be revealed.",
         "このファイルは存在しないため表示できません。"),
    "清除手动指定": ("清除手動指定", "Clear manual override", "手動指定を解除"),
    "在资源管理器中定位": ("在檔案總管中定位", "Reveal in Explorer", "エクスプローラーで表示"),
    "已清除手动指定：{}": ("已清除手動指定：{}", "Cleared override: {}", "手動指定を解除：{}"),
    "这条路径现在不存在，无法定位。":
        ("這條路徑現在不存在，無法定位。", "That path doesn't exist, so it can't be revealed.",
         "このパスは存在しないため表示できません。"),
    "选择「{}」的新位置": ("選擇「{}」的新位置", "Choose a new location for “{}”", "「{}」の新しい場所を選択"),
    "已指定：{} → {}": ("已指定：{} → {}", "Set: {} → {}", "指定：{} → {}"),
    "已指定：{} → {}（该文件当前不存在，请确认）":
        ("已指定：{} → {}（該檔案目前不存在，請確認）",
         "Set: {} → {} (file not found — please check)",
         "指定：{} → {}（ファイルが見つかりません。確認してください）"),
    "请先点「加载全部」": ("請先點「載入全部」", "Click Load all first", "先に「すべて読み込み」を押してください"),
    "当前没有「路径不存在」的素材。\n\n把右上角「只看」切到「缺失」，就能看到这些条目。":
        ("目前沒有「路徑不存在」的素材。\n\n把右上角「只看」切到「缺失」，就能看到這些項目。",
         "No assets with a missing path right now.\n\nSwitch the “Show” filter to Missing to see them.",
         "パスが見つからない素材はありません。\n\n右上の「表示」を「欠落」にすると確認できます。"),
    "勾选 / 选中的行里没有「路径不存在」的素材。\n\n取消勾选，或把「只看」切到「缺失」再试。":
        ("勾選 / 選取的行裡沒有「路徑不存在」的素材。\n\n取消勾選，或把「只看」切到「缺失」再試。",
         "None of the ticked / selected rows have a missing path.\n\n"
         "Clear the ticks, or switch “Show” to Missing and try again.",
         "チェック / 選択した行にパス欠落の素材はありません。\n\n"
         "チェックを外すか、「表示」を「欠落」にして再試行してください。"),
    "要处理 {} 条缺失素材，数量较多，扫描和匹配会比较慢。\n建议先在表格里选中几行再点「查找缺失…」。\n\n仍要继续吗？":
        ("要處理 {} 條缺失素材，數量較多，掃描和比對會比較慢。\n建議先在表格裡選取幾行再點「尋找缺失…」。\n\n仍要繼續嗎？",
         "About to process {} missing assets — scanning and matching will take a while.\nConsider selecting a few rows first.\n\nContinue anyway?",
         "{} 件の欠落素材を処理します。件数が多いと時間がかかります。\n先に数行選択することをおすすめします。\n\n続行しますか？"),
    "查找缺失素材": ("尋找缺失素材", "Find missing assets", "欠落素材を検索"),
    "在下面的目录里按文件名找这些缺失素材，比的是文件名前缀，后缀不同也能认出来。":
        ("在下面的目錄裡按檔名找這些缺失素材，比的是檔名前綴，副檔名不同也能認出來。",
         "Searches the folder below for these missing assets by filename prefix — "
         "a different extension is still recognised.",
         "下のフォルダでファイル名の接頭辞から欠落素材を探します（拡張子が違っても認識します）。"),
    "（范围：已勾选的 {} 条）": ("（範圍：已勾選的 {} 條）", " (scope: {} ticked)", "（範囲：チェック済み {} 件）"),
    "（范围：已选中的 {} 条）": ("（範圍：已選取的 {} 條）", " (scope: {} selected)", "（範囲：選択中 {} 件）"),
    "（范围：全部缺失素材 {} 条）":
        ("（範圍：全部缺失素材 {} 條）", " (scope: all {} missing assets)", "（範囲：欠落素材すべて {} 件）"),
    "搜索目录": ("搜尋目錄", "Search folder", "検索フォルダ"),
    "点「浏览…」选一个目录（会递归扫描子目录）":
        ("點「瀏覽…」選一個目錄（會遞迴掃描子目錄）",
         "Click Browse… to pick a folder (subfolders are scanned too)",
         "「参照…」でフォルダを選択（サブフォルダも走査します）"),
    "相似度": ("相似度", "Similarity", "類似度"),
    "宽松": ("寬鬆", "Loose", "ゆるい"),
    "标准": ("標準", "Normal", "標準"),
    "严格": ("嚴格", "Strict", "厳しい"),
    "搜索深度": ("搜尋深度", "Depth", "検索深度"),
    "3 层": ("3 層", "3 levels", "3 階層"),
    "6 层": ("6 層", "6 levels", "6 階層"),
    "不限": ("不限", "No limit", "制限なし"),
    "后缀": ("副檔名", "Extension", "拡張子"),
    "忽略": ("忽略", "Ignore", "無視"),
    "相同": ("相同", "Must match", "一致"),
    "按文件名前缀比对；后缀选「忽略」时 flv/mp4/mov 互相认。":
        ("按檔名前綴比對；副檔名選「忽略」時 flv/mp4/mov 互相認。",
         "Matched by filename prefix; with Extension = Ignore, flv/mp4/mov are treated as the same.",
         "ファイル名の接頭辞で照合。「拡張子＝無視」なら flv/mp4/mov を同一視します。"),
    "开始扫描": ("開始掃描", "Scan", "スキャン開始"),
    "应用到重定向表": ("套用到重定向表", "Apply to remap list", "再指定リストに適用"),
    "建议文件": ("建議檔案", "Suggested file", "候補ファイル"),
    "所在目录": ("所在目錄", "Folder", "フォルダ"),
    "选好目录和相似度后点「开始扫描」\n\n结果里按住 Ctrl 可多选，确认后点「应用到重定向表」":
        ("選好目錄和相似度後點「開始掃描」\n\n結果裡按住 Ctrl 可多選，確認後點「套用到重定向表」",
         "Pick a folder and similarity, then click Scan\n\nCtrl-click to multi-select, then click Apply to remap list",
         "フォルダと類似度を選んで「スキャン開始」\n\nCtrl+クリックで複数選択し、「再指定リストに適用」を押します"),
    "选好目录和相似度后点「开始扫描」\n\n不选任何行直接点「应用到重定向表」= 全部应用":
        ("選好目錄和相似度後點「開始掃描」\n\n不選任何行直接點「套用到重定向表」= 全部套用",
         "Pick a folder and similarity, then click Scan\n\n"
         "Click Apply to remap list without selecting rows to apply everything",
         "フォルダと類似度を選んで「スキャン開始」\n\n"
         "行を選ばずに「再指定リストに適用」を押すと全件に適用します"),
    "每个素材只留最佳候选":
        ("每個素材只留最佳候選", "Best match only", "各素材は最良候補のみ"),
    "　└ 备选": ("　└ 備選", "  └ alt.", "　└ 候補"),
    "索引 {} 个文件，命中 {} 条素材 / {} 条候选，已自动选中 {} 条（相似度 ≥85%）":
        ("索引 {} 個檔案，命中 {} 條素材 / {} 條候選，已自動選取 {} 條（相似度 ≥85%）",
         "Indexed {} files — {} assets, {} candidates, {} pre-selected (score ≥85%)",
         "{} 件を索引化、素材 {} 件 / 候補 {} 件、{} 件を自動選択（類似度 85% 以上）"),
    "表格里还没有候选，先点「开始扫描」":
        ("表格裡還沒有候選，先點「開始掃描」",
         "No candidates yet — click Scan first",
         "候補がありません。先に「スキャン開始」を押してください"),
    "要把 {} 条素材的建议路径全部填进重定向表吗？\n\n"
    "填完可以在主表里逐条复核，改错了用「清空手动指定」撤回。":
        ("要把 {} 條素材的建議路徑全部填進重定向表嗎？\n\n"
         "填完可以在主表裡逐條複核，改錯了用「清空手動指定」撤回。",
         "Fill the suggested path for all {} assets into the remap list?\n\n"
         "You can review each row afterwards; Clear overrides undoes it.",
         "{} 件すべての候補パスを再指定リストに反映しますか？\n\n"
         "反映後に 1 行ずつ確認できます。間違えたら「手動指定をクリア」で戻せます。"),
    "提示：相似度 ≥85% 的结果会自动选中；不选任何行点「应用到重定向表」= 全部应用。":
        ("提示：相似度 ≥85% 的結果會自動選取；不選任何行點「套用到重定向表」= 全部套用。",
         "Tip: results scoring ≥85% are pre-selected; clicking Apply without "
         "selecting rows applies everything.",
         "ヒント：類似度 85% 以上の結果は自動選択されます。行を選ばずに"
         "「再指定リストに適用」を押すと全件に適用されます。"),
    "请先选一个存在的搜索目录":
        ("請先選一個存在的搜尋目錄", "Please pick an existing search folder", "存在する検索フォルダを選んでください"),
    "正在扫描目录…": ("正在掃描目錄…", "Scanning folder…", "フォルダをスキャン中…"),
    "索引 {} 个文件，开始匹配…":
        ("索引 {} 個檔案，開始比對…", "Indexed {} files — matching…", "{} 件を索引化、照合中…"),
    "出错：{}": ("出錯：{}", "Error: {}", "エラー：{}"),
    "　⚠ 已达文件数上限，建议缩小搜索目录或降低深度":
        ("　⚠ 已達檔案數上限，建議縮小搜尋目錄或降低深度",
         "  ⚠ File cap reached — narrow the folder or reduce depth",
         "  ⚠ ファイル数の上限に達しました。範囲を狭めるか深度を下げてください"),
    "这个目录里没找到相似的文件\n\n试试放宽相似度、加大搜索深度，或换一个目录":
        ("這個目錄裡沒找到相似的檔案\n\n試試放寬相似度、加大搜尋深度，或換一個目錄",
         "No similar files found in this folder\n\nTry a looser similarity, greater depth, or another folder",
         "このフォルダには似たファイルがありません\n\n類似度をゆるめる、深度を上げる、別のフォルダを試してください"),
    "已把 {} 条建议填进重定向表":
        ("已把 {} 條建議填進重定向表", "Filled {} suggestions into the remap list", "{} 件の候補を再指定リストに反映しました"),
    "已为 {} 条缺失素材填上建议路径":
        ("已為 {} 條缺失素材填上建議路徑", "Filled suggested paths for {} missing assets", "{} 件の欠落素材に候補パスを設定しました"),
    "选择要搜索的目录": ("選擇要搜尋的目錄", "Choose a folder to search", "検索するフォルダを選択"),
    "请填写「原路径前缀」": ("請填寫「原路徑前綴」", "Please fill in the old path prefix", "「元のパス接頭辞」を入力してください"),
    "请先选择项目文件": ("請先選擇專案檔", "Please choose a project file", "プロジェクトを選んでください"),
    "读取项目…": ("讀取專案…", "Reading project…", "プロジェクトを読み込み中…"),
    "正在读取素材路径…": ("正在讀取素材路徑…", "Reading asset paths…", "素材パスを読み込み中…"),
    "请先在「规则表」里添加至少一条规则":
        ("請先在「規則表」裡新增至少一條規則",
         "Add at least one rule in Rules… first", "「ルール表」にルールを 1 つ以上追加してください"),
    "已套用 {} 条规则": ("已套用 {} 條規則", "Applied {} rules", "{} 件のルールを適用しました"),
    "（{} 条手动指定保持不变）": ("（{} 條手動指定保持不變）", " ({} manual overrides kept)", "（手動指定 {} 件は保持）"),
    "没有手动指定的条目": ("沒有手動指定的項目", "No manual overrides", "手動指定はありません"),
    "已清除 {} 条手动指定": ("已清除 {} 條手動指定", "Cleared {} manual overrides", "手動指定 {} 件を解除しました"),
    "已加载 {} 条路径　双击任意一行可单独指定新位置":
        ("已載入 {} 條路徑　雙擊任意一行可單獨指定新位置",
         "Loaded {} paths — double-click a row to set its new location",
         "{} 件のパスを読み込みました　行をダブルクリックで個別指定できます"),
    "没有符合条件的条目": ("沒有符合條件的項目", "No items match the filter", "条件に合う項目がありません"),
    "（筛选：{}）": ("（篩選：{}）", " (filter: {})", "（絞り込み：{}）"),
    "共 {} 条，已改写 {} 条，路径缺失 {} 条{}　当前显示 {} 行":
        ("共 {} 條，已改寫 {} 條，路徑缺失 {} 條{}　目前顯示 {} 行",
         "{} total, {} rewritten, {} missing{} — {} rows shown",
         "全 {} 件、書き換え {} 件、欠落 {} 件{}　{} 行を表示中"),
    "保存新清单": ("另存新清單", "Save new list", "新しいリストを保存"),
    "保存 CSV": ("另存 CSV", "Save CSV", "CSV を保存"),
    "导出新文件": ("匯出新檔案", "Save new project", "新ファイル出力"),
    "保存改写后的项目":
        ("另存改寫後的專案", "Save rewritten project", "書き換え後のプロジェクトを保存"),
    "不能覆盖原工程文件。\n\n请换一个文件名（比如加「_重定向」后缀）。":
        ("不能覆蓋原工程檔案。\n\n請換一個檔名（例如加「_重定向」後綴）。",
         "The original project can't be overwritten.\n\n"
         "Please pick another filename (e.g. add a “_remap” suffix).",
         "元のプロジェクトは上書きできません。\n\n"
         "別のファイル名にしてください（例：「_再指定」を付ける）。"),
    "改动来源": ("改動來源", "Source", "変更元"),
    "新路径是否存在": ("新路徑是否存在", "New path exists", "新パスの有無"),
    "手动指定": ("手動指定", "Manual", "手動指定"),
    "规则": ("規則", "Rule", "ルール"),
    "未改": ("未改", "Unchanged", "未変更"),
    "是": ("是", "Yes", "はい"),
    "否": ("否", "No", "いいえ"),
    "改写失败：{}": ("改寫失敗：{}", "Rewrite failed: {}", "書き換えに失敗：{}"),
    "，其中 {} 条来自你手动指定的位置。":
        ("，其中 {} 條來自你手動指定的位置。", " ({} from your manual picks).", "（うち {} 件は手動指定）。"),
    "。\n\n建议先在 Premiere 里打开它确认素材都在线，再决定是否替换原项目。":
        ("。\n\n建議先在 Premiere 裡開啟它確認素材都在線，再決定是否取代原專案。",
         ".\n\nOpen it in Premiere first to confirm all media is online before replacing the original.",
         "。\n\nPremiere で開いてメディアがオンラインか確認してから置き換えてください。"),

    # ---- 页面④ 使用统计 ----
    "开始统计": ("開始統計", "Analyze", "集計開始"),
    "素材总数": ("素材總數", "Total assets", "素材総数"),
    "已使用": ("已使用", "Used", "使用済み"),
    "从未使用": ("從未使用", "Never used", "未使用"),
    "序列数": ("序列數", "Sequences", "シーケンス数"),
    "时间线总时长": ("時間軸總長度", "Total duration", "タイムライン合計"),
    "按使用次数升序排列，没用过的排最前":
        ("按使用次數升冪排列，沒用過的排最前",
         "Sorted by usage count, never-used first",
         "使用回数の昇順、未使用が先頭"),
    "使用次数": ("使用次數", "Uses", "使用回数"),
    "累计时长": ("累計長度", "Duration", "合計時間"),
    "出现在序列": ("出現在序列", "Sequences", "使用シーケンス"),
    "选择项目文件后点「开始统计」\n\n会读取时间线上每个序列，统计每个素材被用了几次、共多长":
        ("選擇專案檔後點「開始統計」\n\n會讀取時間軸上每個序列，統計每個素材被用了幾次、共多長",
         "Pick a project file, then click Analyze\n\nReads every sequence and counts how often / how long each asset is used",
         "プロジェクトを選んで「集計開始」\n\n各シーケンスを読み、素材ごとの使用回数と合計時間を集計します"),
    "分析时间线…": ("分析時間軸…", "Analyzing timeline…", "タイムラインを分析中…"),
    "正在分析时间线…": ("正在分析時間軸…", "Analyzing timeline…", "タイムラインを分析中…"),
    "统计完成：{} 个素材，已用 {}，从未使用 {}，共 {} 个序列":
        ("統計完成：{} 個素材，已用 {}，從未使用 {}，共 {} 個序列",
         "Done: {} assets, {} used, {} never used, {} sequences",
         "完了：素材 {} 件、使用 {} 件、未使用 {} 件、シーケンス {} 個"),
    "保存使用统计": ("另存使用統計", "Save usage report", "使用状況を保存"),
    "AE 工程暂不支持时间线统计（.aep 只做素材路径提取）":
        ("AE 工程暫不支援時間軸統計（.aep 只做素材路徑擷取）",
         "Timeline analysis is not supported for .aep (AE projects are path-extraction only)",
         ".aep のタイムライン集計には未対応（パス抽出のみ）"),
    "Audition 工程暂不支持时间线统计（.sesx 只做素材路径提取）":
        ("Audition 工程暫不支援時間軸統計（.sesx 只做素材路徑擷取）",
         "Timeline analysis is not supported for .sesx (Audition projects are path-extraction only)",
         ".sesx のタイムライン集計には未対応（パス抽出のみ）"),
    "（已跳过：AE 工程不做时间线统计）":
        ("（已跳過：AE 工程不做時間軸統計）", " (skipped: no timeline analysis for .aep)", "（.aep はタイムライン集計対象外）"),

    # ---- v1.0.0 第五轮：.sesx 改写 / 对比联动 / 文件信息 / 分组汇总 ----
    "大小":
        ("大小",
         "Size",
         "サイズ"),
    "修改时间":
        ("修改時間",
         "Modified",
         "更新日時"),
    "素材数":
        ("素材數",
         "Assets",
         "素材数"),
    "占用空间":
        ("佔用空間",
         "Size on disk",
         "使用容量"),
    "文件夹 / 类型":
        ("資料夾 / 類型",
         "Folder / Type",
         "フォルダ / 種類"),
    "视图":
        ("檢視",
         "View",
         "表示"),
    "按文件夹":
        ("按資料夾",
         "By folder",
         "フォルダ別"),
    "按类型":
        ("按類型",
         "By type",
         "種類別"),
    "填到重定向表":
        ("填到重定向表",
         "Fill remap list",
         "再指定リストに反映"),
    "同时提炼前缀规则":
        ("同時提煉前綴規則",
         "Also distill prefix rules",
         "プレフィックスルールも作成"),
    "同时另存改写后的工程文件（不覆盖原文件）":
        ("同時另存改寫後的專案檔（不覆蓋原檔）",
         "Also save the rewritten project (never overwrites the original)",
         "書き換え後のプロジェクトも保存（元ファイルは上書きしません）"),
    "读取候选文件信息…":
        ("讀取候選檔案資訊…",
         "Reading candidate file info…",
         "候補ファイルの情報を読み取り中…"),
    "已把文件夹填进搜索目录":
        ("已把資料夾填進搜尋目錄",
         "Folder placed in the search directory",
         "フォルダを検索ディレクトリに入れました"),
    "已拖入搜索目录：{}　点「开始扫描」":
        ("已拖入搜尋目錄：{}　點「開始掃描」",
         "Search directory set to: {} — click \"Scan\"",
         "検索ディレクトリ：{}　「スキャン開始」を押してください"),
    "拖进来的是文件，不是文件夹。请拖一个目录过来。":
        ("拖進來的是檔案，不是資料夾。請拖一個目錄過來。",
         "That's a file, not a folder. Please drop a folder.",
         "ファイルがドロップされました。フォルダをドロップしてください。"),
    "拖入的是文件夹。搜索目录在「查找缺失…」窗口里 —— 先打开它，再把文件夹拖到那个窗口上。":
        ("拖入的是資料夾。搜尋目錄在「尋找缺失…」視窗裡 —— 先開啟它，再把資料夾拖到那個視窗上。",
         "That's a folder. The search directory lives in the \"Find missing…\" window — open it first, then drop the folder there.",
         "フォルダがドロップされました。検索ディレクトリは「欠落を検索…」ウィンドウにあります。先に開いてから、そのウィンドウにフォルダをドロップしてください。"),
    "汇总完成：{} 组，共 {} 个素材{}":
        ("彙總完成：{} 組，共 {} 個素材{}",
         "Grouped: {} groups, {} assets{}",
         "集計完了：{} グループ、{} 素材{}"),
    "先点「开始对比」":
        ("先點「開始比對」",
         "Click \"Compare\" first",
         "先に「比較開始」を押してください"),
    "这次对比里没有「路径变化」的条目，没什么可填的。\n\n如果只是新增或删除了素材，重定向页用不上。":
        ("這次比對裡沒有「路徑變化」的項目，沒什麼可填的。\n\n如果只是新增或刪除了素材，重定向頁用不上。",
         "This comparison has no \"path changed\" entries, so there's nothing to fill.\n\nIf only assets were added or removed, the Remap tab isn't needed.",
         "今回の比較には「パス変更」の項目がないため、反映するものがありません。\n\n素材の追加・削除だけなら、再指定タブは不要です。"),
    "已把 A（旧项目）填进重定向页　点「加载全部」，再回来点一次「填到重定向表」":
        ("已把 A（舊專案）填進重定向頁　點「載入全部」，再回來點一次「填到重定向表」",
         "A (old project) loaded into the Remap tab — click \"Load all\", then click \"Fill remap list\" again",
         "A（旧プロジェクト）を再指定タブに入れました。「すべて読み込み」を押してから、もう一度「再指定リストに反映」を押してください"),
    "已把 A（旧项目）填进重定向页。\n\n先点「加载全部」把素材列出来，再回来点一次「填到重定向表」，就会把这 {} 条新路径逐条填进去。":
        ("已把 A（舊專案）填進重定向頁。\n\n先點「載入全部」把素材列出來，再回來點一次「填到重定向表」，就會把這 {} 條新路徑逐條填進去。",
         "A (old project) is now in the Remap tab.\n\nClick \"Load all\" to list the assets, then click \"Fill remap list\" again — the {} new paths will be filled in one by one.",
         "A（旧プロジェクト）を再指定タブに入れました。\n\n先に「すべて読み込み」で素材を一覧にしてから、もう一度「再指定リストに反映」を押すと、{} 件の新しいパスが 1 件ずつ入力されます。"),
    "重定向页现在加载的是：\n{}\n\n对比的 A（旧项目）是：\n{}\n\n两边不是同一个项目，路径可能对不上。仍要按 A 的路径填吗？":
        ("重定向頁現在載入的是：\n{}\n\n比對的 A（舊專案）是：\n{}\n\n兩邊不是同一個專案，路徑可能對不上。仍要按 A 的路徑填嗎？",
         "The Remap tab currently has:\n{}\n\nA (old project) in this comparison is:\n{}\n\nThese are different projects, so the paths may not line up. Fill from A anyway?",
         "再指定タブで読み込んでいるのは：\n{}\n\n比較の A（旧プロジェクト）は：\n{}\n\n別のプロジェクトなので、パスが一致しない可能性があります。それでも A のパスで入力しますか？"),
    "其中 {} 条已经有手动指定的新位置，会被这次对比的结果覆盖。\n\n继续吗？":
        ("其中 {} 條已經有手動指定的新位置，會被這次比對的結果覆蓋。\n\n繼續嗎？",
         "{} of them already have a manually picked location, which this comparison result will overwrite.\n\nContinue?",
         "このうち {} 件は手動指定の新しい場所があり、今回の比較結果で上書きされます。\n\n続行しますか？"),
    "重定向表里没有和这些旧路径对得上的条目。\n\n多半是加载的项目不是对比里的 A（旧项目）。":
        ("重定向表裡沒有和這些舊路徑對得上的項目。\n\n多半是載入的專案不是比對裡的 A（舊專案）。",
         "Nothing in the remap list matches those old paths.\n\nMost likely the loaded project isn't A (the old one) from this comparison.",
         "再指定リストに、これらの旧パスと一致する項目がありません。\n\n読み込んだプロジェクトが比較の A（旧プロジェクト）ではない可能性があります。"),
    "已按对比结果指定 {} 条新路径":
        ("已按比對結果指定 {} 條新路徑",
         "{} new paths set from the comparison",
         "比較結果から {} 件の新しいパスを指定しました"),
    "，另添加了 {} 条前缀规则":
        ("，另新增了 {} 條前綴規則",
         ", plus {} prefix rules added",
         "、さらに {} 件のプレフィックスルールを追加しました"),
    "已按对比结果填好 {} 条新路径。":
        ("已按比對結果填好 {} 條新路徑。",
         "Filled in {} new paths from the comparison result.",
         "比較結果から {} 件の新しいパスを入力しました。"),
    "\n\n另外把这次变化提炼成 {} 条前缀规则，放在「规则表…」里，以后新增的素材也能自动套用。":
        ("\n\n另外把這次變化提煉成 {} 條前綴規則，放在「規則表…」裡，以後新增的素材也能自動套用。",
         "\n\nAlso distilled these changes into {} prefix rules in the Rules dialog, so newly added assets get remapped automatically.",
         "\n\nまた今回の変化を {} 件のプレフィックスルールにまとめ、「ルール一覧…」に追加しました。今後追加する素材にも自動適用されます。"),
    "\n\n检查无误后，在重定向页点「导出新文件」生成改写后的工程。":
        ("\n\n檢查無誤後，在重定向頁點「匯出新檔案」產生改寫後的專案。",
         "\n\nWhen everything looks right, click \"Export new file\" on the Remap tab to write the rewritten project.",
         "\n\n確認できたら、再指定タブの「新規ファイルを書き出す」で書き換え後のプロジェクトを出力します。"),
    "AE 工程暂不支持改写（改写只适用于 .prproj / .sesx）":
        ("AE 專案暫不支援改寫（改寫只適用於 .prproj / .sesx）",
         "Rewriting AE projects isn't supported yet (only .prproj / .sesx)",
         "AE プロジェクトの書き換えは未対応です（.prproj / .sesx のみ）"),
    "已另存改写后的项目（原文件未改动）：\n{}":
        ("已另存改寫後的專案（原檔案未改動）：\n{}",
         "Saved the rewritten project (original untouched):\n{}",
         "書き換え後のプロジェクトを保存しました（元ファイルは未変更）：\n{}"),
    "已另存改写后的 Audition 会话（原文件未改动）：\n{}":
        ("已另存改寫後的 Audition 會話（原檔案未改動）：\n{}",
         "Saved the rewritten Audition session (original untouched):\n{}",
         "書き換え後の Audition セッションを保存しました（元ファイルは未変更）：\n{}"),
    "共改写 {} 条路径{}":
        ("共改寫 {} 條路徑{}",
         "{} paths rewritten{}",
         "{} 件のパスを書き換えました{}"),
    "。\n\n建议先在 Audition 里打开它确认素材都在线，再决定是否替换原会话。":
        ("。\n\n建議先在 Audition 裡開啟它確認素材都在線，再決定是否取代原會話。",
         ".\n\nOpen it in Audition first to confirm every asset is online before replacing the original session.",
         "。\n\n先に Audition で開いて素材がすべてオンラインか確認してから、元のセッションを置き換えてください。"),

    # ---- 检查更新 ----
    "检查更新": ("檢查更新", "Check for updates", "アップデートを確認"),
    "正在检查更新…（GitHub / Gitee）":
        ("正在檢查更新…（GitHub / Gitee）",
         "Checking for updates… (GitHub / Gitee)",
         "アップデートを確認中…（GitHub / Gitee）"),
    "发现新版本": ("發現新版本", "Update available", "新しいバージョンがあります"),
    "已是最新版本": ("已是最新版本", "You're up to date", "最新バージョンです"),
    "无法获取最新版本": ("無法取得最新版本", "Couldn't get the latest version",
                        "最新バージョンを取得できません"),
    "当前版本": ("目前版本", "Current version", "現在のバージョン"),
    "最新版本": ("最新版本", "Latest version", "最新バージョン"),
    "未知": ("未知", "Unknown", "不明"),
    "下载地址": ("下載位址", "Download links", "ダウンロード先"),
    "提取码：": ("提取碼：", "Password: ", "パスワード："),
    "复制": ("複製", "Copy", "コピー"),
    "已复制": ("已複製", "Copied", "コピーしました"),
    "关闭": ("關閉", "Close", "閉じる"),
    "蓝奏云": ("藍奏雲", "Lanzou", "藍奏雲"),
    "版本号取自 GitHub / Gitee 的最新 Release tag。下载后解压覆盖即可，配置文件不会丢。":
        ("版本號取自 GitHub / Gitee 最新的 Release tag。下載後解壓覆蓋即可，設定檔不會遺失。",
         "The version comes from the newest GitHub / Gitee release tag. "
         "Unzip over the old folder to update — your config file stays put.",
         "バージョンは GitHub / Gitee の最新 Release タグから取得。"
         "上書き解凍で更新でき、設定ファイルはそのまま残ります。"),
    "通过 {} 获取": ("透過 {} 取得", "via {}", "{} 経由"),
    "发现新版本 {}（当前 {}）{}":
        ("發現新版本 {}（目前 {}）{}",
         "New version {} available (current {}){}",
         "新しいバージョン {} があります（現在 {}）{}"),
    "已是最新版本（{}）{}":
        ("已是最新版本（{}）{}", "Already up to date ({}){}", "最新バージョンです（{}）{}"),
    "检查更新失败：{}":
        ("檢查更新失敗：{}", "Update check failed: {}", "アップデート確認に失敗しました：{}"),
}

I18N = {"zh-TW": {}, "en": {}, "ja": {}}
for _k, (_tw, _en, _ja) in _T.items():
    I18N["zh-TW"][_k] = _tw
    I18N["en"][_k] = _en
    I18N["ja"][_k] = _ja

I18N_KEYS = set(_T)


def tr(s):
    """把中文原文翻成当前语言；没有译文就原样返回"""
    if LANG == "zh-CN" or not s:
        return s
    return I18N.get(LANG, {}).get(s, s)


def set_current(code):
    """切到指定语言（只改模块变量，界面刷新由调用方负责）"""
    global LANG
    if code in CODES:
        LANG = code
    return LANG


# ---------------------------------------------------------------- 系统语言检测
# Windows 的 LANGID：低 10 位是主语言，完整值区分地区。
# 中文必须按完整值判断，否则「中文（台湾）」会被当成简体。
_WIN_LANGID = {
    0x0804: "zh-CN",   # 中文（中国）
    0x1004: "zh-CN",   # 中文（新加坡）
    0x0004: "zh-CN",   # 中文（中性）
    0x0404: "zh-TW",   # 中文（台湾）
    0x0C04: "zh-TW",   # 中文（香港）
    0x1404: "zh-TW",   # 中文（澳门）
    0x0411: "ja",      # 日本語
    0x0011: "ja",
    0x0409: "en", 0x0809: "en", 0x0C09: "en",
    0x1009: "en", 0x1409: "en", 0x1809: "en",
    0x2009: "en", 0x2409: "en", 0x2809: "en",
    0x2C09: "en", 0x3009: "en", 0x3409: "en",
}


def _from_locale_tag(tag):
    """'zh_CN.UTF-8' / 'ja-JP' / 'en_US' → 语言代码；不认识的返回 None"""
    t = (tag or "").strip().lower().replace("_", "-")
    if not t:
        return None
    if t.startswith("zh"):
        # 繁体区：台湾 / 香港 / 澳门，或显式标了 Hant
        if any(k in t for k in ("-tw", "-hk", "-mo", "hant", "traditional")):
            return "zh-TW"
        return "zh-CN"
    if t.startswith("ja"):
        return "ja"
    if t.startswith("en"):
        return "en"
    return None


def detect_system_lang():
    """猜系统语言。认得出就返回受支持的语言代码，认不出返回 None。"""
    # ① Windows：直接问系统 UI 语言，最准（不受 PYTHONIOENCODING 之类影响）
    if sys.platform == "win32":
        try:
            import ctypes
            lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if lid:
                hit = _WIN_LANGID.get(lid & 0xFFFF)
                if hit:
                    return hit
                prim = lid & 0x3FF
                if prim == 0x04:
                    return "zh-CN"
                if prim == 0x11:
                    return "ja"
                if prim == 0x09:
                    return "en"
                return None
        except Exception:
            pass

    # ② macOS / Linux：看环境变量
    for env in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        raw = os.environ.get(env, "")
        # LANGUAGE 可能是 "zh_CN:zh:en" 这种列表
        for part in raw.split(":"):
            hit = _from_locale_tag(part)
            if hit:
                return hit

    # ③ 最后问 locale
    try:
        import locale
        for getter in (locale.getlocale, getattr(locale, "getdefaultlocale", None)):
            if getter is None:
                continue
            try:
                val = getter()
            except Exception:
                continue
            tag = val[0] if isinstance(val, (tuple, list)) and val else val
            hit = _from_locale_tag(tag)
            if hit:
                return hit
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- 配置读写
# 配置文件跟程序放一起（exe 旁边 / 项目根目录），拷走绿色版时配置也跟着走。
# 目录不可写时 appinfo.config_path() 会自动退回用户目录。
def _read_lang(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            v = json.load(f).get("lang")
        if v in CODES:
            return v
    except Exception:
        pass
    return None


def load_lang():
    """读上次选的语言；没有配置就按系统语言猜，猜不出用简体中文"""
    hit = _read_lang(config_path())
    if hit:
        return hit
    # 老版本把配置放在 %APPDATA%，读到就顺手迁到新位置
    old = legacy_config_path()
    if os.path.normcase(old) != os.path.normcase(config_path()):
        hit = _read_lang(old)
        if hit:
            save_lang(hit)
            return hit
    # 首次启动（或配置损坏）：自动跟随系统
    return detect_system_lang() or "zh-CN"


def save_lang(lang):
    try:
        p = config_path()
        d = os.path.dirname(p)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"lang": lang}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass        # 存不了就算了，下次启动重新检测

