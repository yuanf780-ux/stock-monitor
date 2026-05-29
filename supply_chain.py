"""
台美股供應鏈上中下游資料庫（雙向連結）
每個 ticker 都可從這裡查到它的上中下游、相關股。
US 股以美股代碼為 key，TW 股以 XXXX.TW 為 key。
"""

SUPPLY_CHAIN = {

    # ──────────────────────────── 台積電 ────────────────────────────────
    "2330.TW": {
        "name": "台積電",
        "desc": "全球最大晶圓代工，3nm/2nm 先進製程龍頭，AI 時代算力核心基礎",
        "themes": ["AI 算力核心", "先進製程 3/2nm", "CoWoS 封裝", "半導體龍頭", "外資長期重倉", "ADR:TSM"],
        "upstream": [
            ("ASML",    "艾司摩爾",   "EUV 光刻機唯一來源"),
            ("AMAT",    "應用材料",   "CVD/PVD 薄膜沉積設備"),
            ("LRCX",    "科磊",       "蝕刻設備主供應商"),
            ("KLAC",    "科磊檢測",   "量測品管設備"),
            ("5483.TW", "中美晶",     "12吋矽晶圓"),
            ("6770.TW", "力積電",     "特殊矽晶圓"),
        ],
        "midstream": [
            ("3711.TW", "日月光投控", "CoWoS/SoIC 先進封裝"),
            ("2408.TW", "南亞科",     "DRAM 搭配記憶體"),
            ("3034.TW", "聯詠",       "驅動 IC"),
        ],
        "downstream": [
            ("NVDA",    "輝達",       "AI GPU H100/B200（最大客戶）"),
            ("AAPL",    "蘋果",       "A18/M4 SoC"),
            ("AMD",     "超微",       "EPYC/MI300 CPU+GPU"),
            ("QCOM",    "高通",       "驍龍手機基頻"),
            ("2454.TW", "聯發科",     "天璣手機 SoC"),
            ("AVGO",    "博通",       "AI ASIC/網路晶片"),
            ("INTC",    "英特爾",     "18A 試產"),
        ],
        "related": [
            ("TSM",     "台積電 ADR",  "美股直接對應"),
            ("2303.TW", "聯電",        "成熟製程競爭對手"),
            ("GFS",     "格芯",        "特殊製程代工"),
        ],
    },

    # ──────────────────────────── 輝達 ────────────────────────────────
    "NVDA": {
        "name": "輝達",
        "desc": "AI GPU 龍頭，H100/B200/GB200 佔據 AI 訓練市場 80%+ 份額，CUDA 生態護城河深",
        "themes": ["AI GPU 龍頭", "CUDA 生態獨佔", "資料中心爆發", "自動駕駛 DRIVE", "機器人 Isaac"],
        "upstream": [
            ("2330.TW", "台積電",     "所有 GPU 唯一代工廠（4nm/3nm）"),
            ("MU",      "美光",       "HBM3/HBM3e 記憶體"),
            ("AMAT",    "應用材料",   "間接：設備供應鏈"),
            ("3711.TW", "日月光",     "CoWoS 封裝"),
        ],
        "midstream": [
            ("2382.TW", "廣達",       "GB200 NVL72 最大組裝廠"),
            ("2356.TW", "英業達",     "HGX AI server OEM"),
            ("6669.TW", "緯穎",       "超大規模 ODM"),
            ("SMCI",    "超微電腦",   "GPU Server 整機品牌"),
            ("3017.TW", "奇鋐",       "液冷散熱模組"),
            ("2308.TW", "台達電",     "高功率電源供應器"),
        ],
        "downstream": [
            ("MSFT",    "微軟",       "Azure AI 最大採購方"),
            ("GOOGL",   "Alphabet",   "GCP TPU+GPU 並用"),
            ("AMZN",    "亞馬遜",     "AWS EC2 P5 執行個體"),
            ("META",    "Meta",       "AI 訓練叢集大戶"),
            ("TSLA",    "特斯拉",     "FSD Dojo AI 訓練"),
        ],
        "related": [
            ("AMD",     "超微",       "GPU MI300 競爭對手"),
            ("INTC",    "英特爾",     "Gaudi AI 加速器"),
            ("AVGO",    "博通",       "客製 ASIC 替代方案"),
        ],
    },

    # ──────────────────────────── 廣達 ────────────────────────────────
    "2382.TW": {
        "name": "廣達",
        "desc": "全球最大 AI 伺服器 ODM，NVIDIA GB200 NVL72 主要組裝商，雲端大廠直接供應",
        "themes": ["AI 伺服器 ODM", "GB200 NVL72", "液冷散熱", "雲端資料中心", "MacBook ODM"],
        "upstream": [
            ("NVDA",    "輝達",       "GPU 核心採購"),
            ("INTC",    "英特爾",     "Xeon 伺服器 CPU"),
            ("AMD",     "超微",       "EPYC CPU（部分）"),
            ("MU",      "美光",       "DDR5/HBM 記憶體"),
            ("3017.TW", "奇鋐",       "液冷散熱模組"),
            ("2308.TW", "台達電",     "電源供應器"),
            ("AAPL",    "蘋果",       "MacBook ODM 客戶"),
        ],
        "midstream": [
            ("6269.TW", "台郡",       "FPC 軟板"),
            ("3034.TW", "聯詠",       "顯示驅動 IC"),
        ],
        "downstream": [
            ("MSFT",    "微軟",       "Azure AI 伺服器主力供應"),
            ("GOOGL",   "Alphabet",   "Google Cloud 採購"),
            ("META",    "Meta",       "AI 訓練機房整機"),
            ("AMZN",    "亞馬遜",     "AWS Trainium 伺服器"),
        ],
        "related": [
            ("2356.TW", "英業達",     "AI 伺服器同業"),
            ("6669.TW", "緯穎",       "超大規模 ODM 競爭"),
            ("SMCI",    "超微電腦",   "美股競爭對手"),
        ],
    },

    # ──────────────────────────── 鴻海 ────────────────────────────────
    "2317.TW": {
        "name": "鴻海",
        "desc": "全球最大 EMS 電子代工，蘋果最大 iPhone 組裝商，積極轉型 AI Server 與電動車 MIH",
        "themes": ["蘋果供應鏈", "EMS 龍頭", "電動車 MIH 平台", "AI 伺服器", "機器人"],
        "upstream": [
            ("AAPL",    "蘋果",       "最大客戶（iPhone 60%+ 組裝）"),
            ("2330.TW", "台積電",     "晶片供應鏈上游"),
            ("2308.TW", "台達電",     "電源/充電模組"),
            ("NVDA",    "輝達",       "AI Server GPU 採購"),
        ],
        "midstream": [
            ("2354.TW", "鴻準",       "集團子公司：機殼精密件"),
            ("6263.TW", "普萊德",     "電動巴士底盤"),
        ],
        "downstream": [
            ("AAPL",    "蘋果",       "iPhone/Mac 組裝出貨"),
            ("TSLA",    "特斯拉",     "EV 合作/代工"),
            ("NVDA",    "輝達",       "AI Server 組裝供應"),
            ("DELL",    "戴爾",       "PC/Server 代工"),
        ],
        "related": [
            ("2354.TW", "鴻準",       "鴻海集團子公司"),
            ("2356.TW", "英業達",     "EMS 同業"),
            ("2382.TW", "廣達",       "AI Server 同業競爭"),
        ],
    },

    # ──────────────────────────── 聯發科 ────────────────────────────────
    "2454.TW": {
        "name": "聯發科",
        "desc": "天璣 SoC 全球第一，積極切入 AI 手機、衛星通訊、車用晶片、ASIC",
        "themes": ["AI 手機晶片", "天璣 SoC", "衛星通訊", "AIoT", "車用晶片", "ASIC"],
        "upstream": [
            ("2330.TW", "台積電",     "4nm/3nm 手機 SoC 代工"),
            ("ARMH",    "ARM",        "CPU 核心架構授權"),
            ("IMGTECH",  "Imagination","GPU IP 授權（部分）"),
        ],
        "midstream": [
            ("3711.TW", "日月光",     "SoC 封測"),
        ],
        "downstream": [
            ("小米",    "Xiaomi",     "最大客戶（天璣系列）"),
            ("OPPO",    "OPPO",       "手機 SoC 採購"),
            ("vivo",    "vivo",       "手機 SoC 採購"),
            ("SAMS",    "三星",       "Galaxy A 系列部分型號"),
        ],
        "related": [
            ("QCOM",    "高通",       "手機晶片最大競爭對手"),
            ("2379.TW", "瑞昱",       "網路/音效 IC 同業"),
            ("MRVL",    "邁威爾",     "資料中心 IC 競爭"),
        ],
    },

    # ──────────────────────────── 蘋果 ────────────────────────────────
    "AAPL": {
        "name": "蘋果",
        "desc": "全球市值最大，iPhone 帶動台灣供應鏈，Apple Intelligence 推動 AI 手機換機潮",
        "themes": ["AI 手機換機潮", "Apple Intelligence", "蘋果供應鏈龍頭", "服務業務高利潤"],
        "upstream": [
            ("2330.TW", "台積電",     "A18/M4 晶片唯一代工"),
            ("2317.TW", "鴻海",       "iPhone 最大組裝廠"),
            ("3008.TW", "大立光",     "iPhone 鏡頭模組龍頭"),
            ("2382.TW", "廣達",       "MacBook ODM"),
            ("2354.TW", "鴻準",       "Mac Pro/Studio 機殼"),
            ("QCOM",    "高通",       "iPhone 基頻晶片（部分）"),
            ("SAMS",    "三星",       "OLED 面板供應"),
            ("2408.TW", "南亞科",     "記憶體"),
        ],
        "midstream": [
            ("6269.TW", "台郡",       "FPC 軟板"),
            ("2308.TW", "台達電",     "電源充電器"),
            ("3008.TW", "大立光",     "鏡頭組裝"),
        ],
        "downstream": [
            ("消費者",  "全球消費者",  "B2C 直售"),
            ("企業客戶","企業市場",    "Mac/iPad 企業部署"),
        ],
        "related": [
            ("GOOGL",   "Alphabet",   "Android 生態系競爭"),
            ("MSFT",    "微軟",       "PC/雲端生態競爭"),
            ("SAMS",    "三星",       "手機+零件競爭/合作"),
        ],
    },

    # ──────────────────────────── 超微電腦 SMCI ─────────────────────────
    "SMCI": {
        "name": "超微電腦",
        "desc": "AI Server 整機品牌，NVIDIA GPU Server 主力供應商，液冷解決方案領先",
        "themes": ["AI Server 整機", "GB200 NVL72", "液冷散熱", "資料中心基礎設施"],
        "upstream": [
            ("NVDA",    "輝達",       "GPU H100/H200/B200 最大採購"),
            ("INTC",    "英特爾",     "Xeon CPU"),
            ("AMD",     "超微",       "EPYC CPU"),
            ("MU",      "美光",       "DDR5/HBM 記憶體"),
            ("2330.TW", "台積電",     "間接：晶片供應鏈"),
            ("3017.TW", "奇鋐",       "液冷散熱模組採購"),
            ("2308.TW", "台達電",     "電源模組"),
        ],
        "midstream": [],
        "downstream": [
            ("MSFT",    "微軟",       "Azure GPU Server"),
            ("GOOGL",   "Alphabet",   "GCP"),
            ("META",    "Meta",       "AI 訓練"),
            ("AMZN",    "亞馬遜",     "AWS"),
        ],
        "related": [
            ("2382.TW", "廣達",       "台灣 ODM 競爭對手"),
            ("2356.TW", "英業達",     "台灣 ODM 競爭"),
            ("HPE",     "惠普企業",   "Server 品牌競爭"),
            ("DELL",    "戴爾",       "Server 品牌競爭"),
        ],
    },

    # ──────────────────────────── 美光 MU ─────────────────────────────
    "MU": {
        "name": "美光科技",
        "desc": "全球第三大記憶體廠，HBM3/HBM3e 為 NVIDIA GPU 核心配套，DRAM/NAND 雙線",
        "themes": ["HBM AI 記憶體", "DRAM 漲價週期", "NAND Flash", "AI 伺服器配套"],
        "upstream": [
            ("AMAT",    "應用材料",   "記憶體製程設備"),
            ("LRCX",    "科磊",       "蝕刻設備"),
            ("ASML",    "艾司摩爾",   "EUV 曝光設備"),
            ("2330.TW", "台積電",     "部分先進製程委外"),
        ],
        "midstream": [
            ("3711.TW", "日月光",     "記憶體封測"),
            ("2408.TW", "南亞科",     "台灣 DRAM 同業"),
        ],
        "downstream": [
            ("NVDA",    "輝達",       "HBM3e 最大客戶"),
            ("AAPL",    "蘋果",       "iPhone/Mac 記憶體"),
            ("DELL",    "戴爾",       "Server 記憶體"),
            ("HPE",     "惠普企業",   "Server 記憶體"),
            ("2382.TW", "廣達",       "AI Server 配套記憶體"),
        ],
        "related": [
            ("2408.TW", "南亞科",     "台灣 DRAM 競爭對手"),
            ("2337.TW", "旺宏",       "NOR Flash 同業"),
            ("WDC",     "威騰",       "NAND Flash 競爭"),
        ],
    },

    # ──────────────────────────── 奇鋐 ─────────────────────────────────
    "3017.TW": {
        "name": "奇鋐",
        "desc": "AI 散熱模組龍頭，液冷/氣冷雙線，NVIDIA GB200 液冷主要供應商",
        "themes": ["AI 散熱龍頭", "液冷模組", "GB200 散熱", "資料中心熱管理"],
        "upstream": [
            ("銅鋁材料", "原材料",    "銅/鋁合金散熱鰭片"),
            ("泵浦廠商", "水泵",      "液冷循環泵"),
        ],
        "midstream": [],
        "downstream": [
            ("NVDA",    "輝達",       "GB200 液冷散熱採購"),
            ("SMCI",    "超微電腦",   "AI Server 散熱整合"),
            ("2382.TW", "廣達",       "AI Server 散熱模組"),
            ("2356.TW", "英業達",     "Server 散熱供應"),
            ("HPE",     "惠普企業",   "企業伺服器散熱"),
        ],
        "related": [
            ("建準",    "建準",       "散熱風扇同業"),
            ("VRT",     "維美德",     "美股液冷競爭對手"),
        ],
    },

    # ──────────────────────────── 台達電 ─────────────────────────────
    "2308.TW": {
        "name": "台達電",
        "desc": "電源管理/工廠自動化龍頭，AI Server 高功率電源供應器主要廠商",
        "themes": ["AI Server 電源", "EV 充電", "工廠自動化", "綠能儲能", "電源管理"],
        "upstream": [
            ("原材料",  "功率元件",   "MOSFET/電容/磁性元件"),
            ("ON",      "安森美",     "功率半導體元件採購"),
        ],
        "midstream": [],
        "downstream": [
            ("NVDA",    "輝達",       "GB200 高效電源供應"),
            ("SMCI",    "超微電腦",   "AI Server 電源"),
            ("2382.TW", "廣達",       "伺服器電源"),
            ("2317.TW", "鴻海",       "電源模組"),
            ("TSLA",    "特斯拉",     "EV 充電站電源"),
        ],
        "related": [
            ("ENPH",    "Enphase",    "太陽能逆變器同業"),
            ("VRT",     "維美德",     "資料中心電源競爭"),
        ],
    },

    # ──────────────────────────── 日月光 ─────────────────────────────
    "3711.TW": {
        "name": "日月光投控",
        "desc": "全球最大半導體封測廠，CoWoS/SoIC 先進封裝為 AI 時代核心技術",
        "themes": ["CoWoS 先進封裝", "AI 晶片封測", "SoIC 異質整合", "半導體後段"],
        "upstream": [
            ("2330.TW", "台積電",     "CoWoS 封裝基板委外"),
            ("AMAT",    "應用材料",   "封裝製程設備"),
            ("基板廠",  "基板廠商",   "ABF 基板"),
        ],
        "midstream": [],
        "downstream": [
            ("NVDA",    "輝達",       "H100/B200 CoWoS 封裝"),
            ("AMD",     "超微",       "MI300 先進封裝"),
            ("AAPL",    "蘋果",       "A18/M4 封測"),
            ("2454.TW", "聯發科",     "天璣 SoC 封測"),
            ("QCOM",    "高通",       "驍龍晶片封測"),
        ],
        "related": [
            ("6533.TW", "矽格",       "封測同業"),
            ("2325.TW", "矽品",       "封測同業（已整合）"),
        ],
    },

    # ──────────────────────────── 大立光 ─────────────────────────────
    "3008.TW": {
        "name": "大立光",
        "desc": "手機鏡頭模組全球龍頭，蘋果 iPhone 最高規格鏡頭長期獨家供應商",
        "themes": ["蘋果鏡頭壟斷", "手機光學", "AI 視覺鏡頭", "潛望式鏡頭"],
        "upstream": [
            ("玻璃廠",  "光學玻璃",   "精密玻璃素材"),
            ("塑料廠",  "光學塑料",   "超精密塑膠射出"),
        ],
        "midstream": [],
        "downstream": [
            ("AAPL",    "蘋果",       "iPhone 高階鏡頭（最大客戶 >75%）"),
            ("2317.TW", "鴻海",       "iPhone 組裝整合"),
            ("安卓廠",  "安卓品牌",   "少量供應"),
        ],
        "related": [
            ("玉晶光",  "玉晶光",     "鏡頭同業"),
            ("COHR",    "Coherent",   "光學元件同業（不同市場）"),
        ],
    },

    # ──────────────────────────── 特斯拉 ─────────────────────────────
    "TSLA": {
        "name": "特斯拉",
        "desc": "電動車龍頭，FSD 自動駕駛領先，Optimus 人形機器人為下一成長引擎，Megapack 儲能規模化",
        "themes": ["電動車龍頭", "FSD 自動駕駛", "Optimus 機器人", "儲能 Megapack", "DOJO AI 訓練"],
        "upstream": [
            ("2330.TW", "台積電",     "FSD 自動駕駛晶片代工"),
            ("NVDA",    "輝達",       "DOJO 訓練叢集 GPU（歷史）"),
            ("2308.TW", "台達電",     "充電站/電源模組"),
            ("PANASONIC","松下",      "4680 圓柱電池合作"),
            ("ALB",     "雅保",       "鋰礦原材料"),
            ("2317.TW", "鴻海",       "MIH 代工合作"),
        ],
        "midstream": [],
        "downstream": [
            ("消費者",  "全球消費者",  "EV 直售"),
            ("企業",    "工商業",      "Megapack 儲能採購"),
        ],
        "related": [
            ("RIVN",    "Rivian",     "美國 EV 競爭對手"),
            ("LI",      "理想汽車",   "中國 EV 競爭"),
            ("NIO",     "蔚來",       "中國 EV 競爭"),
        ],
    },

    # ──────────────────────────── 超微 AMD ─────────────────────────────
    "AMD": {
        "name": "超微",
        "desc": "CPU+GPU 雙核，MI300X AI 加速器快速放量，EPYC 伺服器 CPU 持續奪取 Intel 市佔",
        "themes": ["AI GPU MI300", "EPYC 伺服器 CPU", "CPU 市佔回升", "資料中心"],
        "upstream": [
            ("2330.TW", "台積電",     "5nm/4nm GPU+CPU 代工"),
            ("3711.TW", "日月光",     "MI300 先進封裝"),
            ("MU",      "美光",       "HBM3 記憶體"),
        ],
        "midstream": [
            ("SMCI",    "超微電腦",   "AMD GPU Server 整機"),
            ("2382.TW", "廣達",       "AMD Server ODM"),
            ("HPE",     "惠普企業",   "ProLiant AMD 伺服器"),
        ],
        "downstream": [
            ("MSFT",    "微軟",       "Azure AMD 執行個體"),
            ("GOOGL",   "Alphabet",   "GCP A3 VM AMD"),
            ("META",    "Meta",       "MI300X 大量採購"),
            ("AMZN",    "亞馬遜",     "AWS Graviton+EPYC"),
        ],
        "related": [
            ("NVDA",    "輝達",       "GPU 最大競爭對手"),
            ("INTC",    "英特爾",     "CPU 競爭對手"),
            ("AVGO",    "博通",       "AI ASIC 替代方案"),
        ],
    },

    # ──────────────────────────── 微軟 MSFT ────────────────────────────
    "MSFT": {
        "name": "微軟",
        "desc": "Azure AI 雲端龍頭，Copilot AI 全線整合，OpenAI 獨家合作夥伴",
        "themes": ["Azure AI 雲端", "Copilot AI", "OpenAI 合作", "Office 365 訂閱", "企業軟體"],
        "upstream": [
            ("NVDA",    "輝達",       "Azure GPU 最大採購方"),
            ("2382.TW", "廣達",       "Azure AI Server 主要 ODM"),
            ("SMCI",    "超微電腦",   "Azure GPU Server"),
            ("AMD",     "超微",       "Azure EPYC 執行個體"),
            ("INTC",    "英特爾",     "Azure Intel 執行個體"),
        ],
        "midstream": [],
        "downstream": [
            ("企業客戶","全球企業",    "Azure/Office 365 訂閱"),
            ("開發者",  "開發者",      "GitHub Copilot"),
        ],
        "related": [
            ("GOOGL",   "Alphabet",   "雲端/AI 最大競爭對手"),
            ("AMZN",    "亞馬遜",     "AWS 雲端競爭"),
            ("CRM",     "Salesforce", "CRM/AI 企業軟體競爭"),
        ],
    },

    # ──────────────────────────── 長榮 ─────────────────────────────────
    "2603.TW": {
        "name": "長榮海運",
        "desc": "全球前十大貨櫃航運，受益紅海繞行與供應鏈重組，高現金流高股息",
        "themes": ["航運龍頭", "紅海繞行漲運費", "高股息", "貨櫃航運週期"],
        "upstream": [
            ("造船廠",  "韓/中造船廠",  "新船建造"),
            ("燃油廠",  "燃料油",       "重油/LNG 燃料"),
        ],
        "midstream": [],
        "downstream": [
            ("貨主",    "全球製造業",   "貨櫃運輸需求"),
            ("電商",    "電商物流",     "跨境電商海運"),
        ],
        "related": [
            ("2609.TW", "陽明",        "台灣航運同業"),
            ("2615.TW", "萬海",        "台灣近洋航運"),
            ("ZIM",     "以星航運",     "美股航運對標"),
            ("MATX",    "馬士基",       "美股航運"),
        ],
    },

    # ──────────────────────────── 富邦金 ─────────────────────────────
    "2881.TW": {
        "name": "富邦金",
        "desc": "台灣最大金控，壽險+銀行+證券三大業務，外資長期持股，高殖利率",
        "themes": ["台灣最大金控", "壽險龍頭", "高殖利率", "數位金融", "外資重倉"],
        "upstream": [
            ("投資市場", "資本市場",   "保費投資於股債"),
            ("MSFT",    "微軟",       "Azure 金融雲端"),
        ],
        "midstream": [],
        "downstream": [
            ("保戶",    "個人壽險客戶","壽險保障"),
            ("企業",    "企業金融",    "放款/投資銀行"),
        ],
        "related": [
            ("2882.TW", "國泰金",     "壽險最大競爭對手"),
            ("2886.TW", "兆豐金",     "銀行同業"),
            ("JPM",     "摩根大通",   "美股金融對標"),
        ],
    },

    # ──────────────────────────── 英業達 ─────────────────────────────
    "2356.TW": {
        "name": "英業達",
        "desc": "AI 伺服器 OEM/ODM，HGX AI Server 主要供應商，與廣達並列 AI 伺服器雙雄",
        "themes": ["AI 伺服器 ODM", "HGX Server", "雲端資料中心", "筆電 ODM"],
        "upstream": [
            ("NVDA",    "輝達",       "HGX GPU 採購"),
            ("INTC",    "英特爾",     "Xeon CPU"),
            ("MU",      "美光",       "DDR5 記憶體"),
            ("3017.TW", "奇鋐",       "散熱模組"),
            ("2308.TW", "台達電",     "電源供應器"),
        ],
        "midstream": [],
        "downstream": [
            ("GOOGL",   "Alphabet",   "GCP AI Server"),
            ("AMZN",    "亞馬遜",     "AWS Trainium"),
            ("META",    "Meta",       "AI 訓練機房"),
            ("MSFT",    "微軟",       "Azure AI Server"),
        ],
        "related": [
            ("2382.TW", "廣達",       "AI Server 最大同業"),
            ("6669.TW", "緯穎",       "超大規模 ODM"),
            ("SMCI",    "超微電腦",   "美股競爭對手"),
        ],
    },

    # ──────────────────────────── 緯穎 ─────────────────────────────────
    "6669.TW": {
        "name": "緯穎",
        "desc": "超大規模資料中心 ODM，Meta/Microsoft 最大 Server 供應商之一",
        "themes": ["超大規模 ODM", "AI 伺服器", "Meta 供應鏈", "資料中心"],
        "upstream": [
            ("NVDA",    "輝達",       "GPU 採購"),
            ("INTC",    "英特爾",     "CPU"),
            ("AMD",     "超微",       "EPYC CPU"),
            ("MU",      "美光",       "記憶體"),
        ],
        "midstream": [],
        "downstream": [
            ("META",    "Meta",       "最大客戶"),
            ("MSFT",    "微軟",       "Azure Server"),
            ("GOOGL",   "Alphabet",   "GCP"),
        ],
        "related": [
            ("2382.TW", "廣達",       "AI ODM 競爭"),
            ("2356.TW", "英業達",     "AI ODM 競爭"),
        ],
    },
}


STOCK_THEMES = {
    "2330.TW": ["AI 算力核心", "先進製程 3nm/2nm", "CoWoS 封裝", "半導體龍頭", "外資長期重倉", "ADR:TSM"],
    "2317.TW": ["蘋果供應鏈", "EMS 龍頭", "電動車 MIH", "AI Server", "機器人"],
    "2382.TW": ["AI 伺服器 ODM", "GB200 NVL72", "雲端資料中心", "散熱液冷"],
    "2356.TW": ["AI 伺服器 ODM", "HGX Server", "雲端資料中心"],
    "6669.TW": ["超大規模 ODM", "AI 伺服器", "Meta 供應鏈"],
    "2454.TW": ["AI 手機晶片", "天璣 SoC", "衛星通訊", "AIoT", "車用晶片"],
    "2881.TW": ["台灣最大金控", "壽險龍頭", "高殖利率", "外資重倉"],
    "2603.TW": ["航運龍頭", "紅海繞行", "高股息", "貨櫃週期"],
    "3711.TW": ["CoWoS 先進封裝", "AI 晶片封測", "SoIC 異質整合"],
    "3017.TW": ["AI 散熱龍頭", "液冷模組", "GB200 散熱"],
    "3008.TW": ["蘋果鏡頭壟斷", "手機光學", "AI 視覺"],
    "2308.TW": ["AI Server 電源", "EV 充電", "工廠自動化", "綠能儲能"],
    "NVDA":    ["AI GPU 龍頭", "CUDA 生態獨佔", "資料中心", "自動駕駛", "機器人"],
    "AAPL":    ["AI 手機換機潮", "Apple Intelligence", "蘋果供應鏈帶動"],
    "TSLA":    ["電動車龍頭", "FSD 自動駕駛", "Optimus 機器人", "儲能 Megapack"],
    "AMD":     ["AI GPU MI300", "EPYC 伺服器", "CPU 市佔回升"],
    "MSFT":    ["Azure AI 雲端", "Copilot", "OpenAI 合作", "Office 365"],
    "SMCI":    ["AI Server 整機", "GB200 組裝", "液冷散熱"],
    "MU":      ["HBM3 AI 記憶體", "DRAM 漲價週期", "AI GPU 配套"],
    "AMZN":    ["AWS 雲端", "電商龍頭", "AI Trainium", "物流自動化"],
    "GOOGL":   ["GCP AI 雲端", "Gemini AI", "搜尋龍頭", "自動駕駛 Waymo"],
    "META":    ["AI 訓練最大算力", "Llama AI", "社群媒體", "VR/AR"],
    "QCOM":    ["手機基頻晶片", "驍龍 SoC", "AI 手機", "車用晶片"],
    "AVGO":    ["AI ASIC 客製", "網路晶片", "博通收購整合"],
    "ASML":    ["EUV 光刻機壟斷", "半導體設備", "荷蘭科技"],
    "AMAT":    ["半導體設備", "CVD/PVD 設備", "AI 晶片製程"],
    "LRCX":    ["蝕刻設備龍頭", "半導體設備"],
    "TSM":     ["台積電 ADR", "AI 晶圓代工", "美股直接對應"],
}


def get_supply_chain(ticker: str) -> dict:
    return SUPPLY_CHAIN.get(ticker, {})


def get_themes(ticker: str) -> list:
    return STOCK_THEMES.get(ticker, [])


def get_all_related(ticker: str) -> list:
    """Return all tickers mentioned in this stock's supply chain."""
    chain = SUPPLY_CHAIN.get(ticker, {})
    tickers = set()
    for key in ("upstream", "midstream", "downstream", "related"):
        for t, _, _ in chain.get(key, []):
            if t and not any(c in t for c in ["廠", "者", "卓", "牌", "客", "電商"]):
                tickers.add(t)
    return list(tickers)
