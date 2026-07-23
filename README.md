# 百度翻译新版网页接口逆向分析

这是一个面向学习的 JavaScript 逆向与网络请求复现项目，记录新版百度翻译网页从抓包、定位前端代码、分析 ACS 调用链，到使用 Python 解析 SSE 翻译结果的完整过程。

项目分析的网页入口：

```text
https://fanyi.baidu.com/mtpe-individual/transText
```

> 本项目仅用于学习网页请求、JavaScript 调试和自己有权访问的接口。请勿用于绕过验证码、伪造设备指纹、规避网站访问控制或高频请求。

## 项目现状

- 已定位新版文本翻译接口：`POST /ait/text/translate`
- 已还原网页实际使用的 JSON Payload
- 已实现 `requests.Session` 请求和 SSE 响应解析
- 支持从自己导出的成功 HAR 中读取短期 `Acs-Token`
- 支持一次输入多条文本进行顺序翻译
- 已保存并扫描当前网页的主要 JavaScript 文件
- 已提供格式化、AST 分析、HAR 脱敏和 DevTools Hook 工具

需要注意：这不是百度官方开放 API。网页接口受到 ACS 风控保护，`Acs-Token` 可能很快过期，网站升级后 Payload、接口或前端模块也可能变化。因此本项目适合逆向学习和短期验证，不适合长期无人维护的生产任务。

## 工作原理

当前网页翻译链路可以概括为：

```text
输入翻译文本
  ↓
前端组装JSON Payload和毫秒时间戳
  ↓
Paris/ACS SDK生成短期Acs-Token
  ↓
POST /ait/text/translate
  ↓
服务器返回text/event-stream
  ↓
解析Translating事件中的data.list[*].dst
```

当前主包中定位到的主要 webpack 模块：

| 模块 | 作用 |
|---:|---|
| `35353` | 文本翻译业务和 SSE 状态处理 |
| `83276` | SSE 请求封装和 ACS 配置 |
| `88172` | `getAcsInstance → getSign → Acs-Token` |
| `71890` | 风控验证码和 `svcp_stk` Cookie |

详细静态扫描结果见 [ANALYSIS.generated.md](./ANALYSIS.generated.md)。

## 主程序

真正用于发起翻译请求的主程序只有：

```text
baidu_web_translate.py
```

其余目录主要用于保存原始证据、分析 JavaScript 和运行测试。

## 环境要求

- Python 3.10 或更高版本
- `requests`
- Node.js 18 或更高版本，仅在使用 JavaScript 分析工具时需要

安装 Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

如果需要运行 AST、Prettier 等 JavaScript 分析工具：

```powershell
npm.cmd install
```

Windows PowerShell 可能禁止执行 `npm.ps1`，这种情况下直接使用 `npm.cmd`。

## 快速开始

### 1. 查看请求结构但不联网

```powershell
python .\baidu_web_translate.py --dry-run "hello"
```

### 2. 不使用 HAR 尝试请求

```powershell
python .\baidu_web_translate.py "hello"
```

如果返回以下错误：

```text
errno=995, request is not authorized
```

说明百度要求本次请求携带浏览器生成的 ACS 上下文，需要使用近期成功 HAR。

### 3. 使用成功 HAR 翻译

```powershell
python .\baidu_web_translate.py --har "D:\path\baidu-success.har" "hello"
```

成功输出示例：

```json
{"source": "hello", "target": "你好", "from_lang": "en", "to_lang": "zh"}
```

HAR 文件扩展名不影响解析，只要内容是合法 HAR JSON，使用 `.har` 或 `.txt` 都可以。

### 4. 批量翻译

每段文本分别作为一个命令行参数：

```powershell
python .\baidu_web_translate.py `
  --har "D:\path\baidu-success.har" `
  "hello" `
  "Good morning" `
  "Python is easy to learn"
```

程序会顺序发送请求，并在请求之间随机等待，避免瞬间并发。

### 5. 指定语言

```powershell
python .\baidu_web_translate.py `
  --har "D:\path\baidu-success.har" `
  --from-lang en `
  --to-lang zh `
  "hello"
```

## 如何获取成功 HAR

1. 使用浏览器打开：

   ```text
   https://fanyi.baidu.com/mtpe-individual/transText
   ```

2. 按 `F12` 打开开发者工具，进入 **Network**。
3. 勾选 **Preserve log** 和 **Disable cache**。
4. 在网页中正常翻译一次，例如输入 `hello`。
5. 在 Network 中找到 `/ait/text/translate`。
6. 确认请求状态为 `200`，响应类型为 `text/event-stream`。
7. 导出 HAR，然后通过 `--har` 传给主程序。

HAR 可能包含 Cookie、短期 ACS Token 和其他浏览器信息：

- 不要将原始 HAR 上传到 GitHub
- 不要将完整 HAR 粘贴到公开聊天或论坛
- 不要在代码中硬编码完整 `Acs-Token`
- Token 过期并再次出现 `995` 时，需要重新导出成功 HAR

## 实际请求结构

成功抓包中的主要请求结构：

```http
POST /ait/text/translate HTTP/1.1
Host: fanyi.baidu.com
Accept: text/event-stream
Content-Type: application/json
Acs-Token: <动态短期值>
Origin: https://fanyi.baidu.com
Referer: https://fanyi.baidu.com/mtpe-individual/transText
```

Payload 示例：

```json
{
  "needNewlineCombine": false,
  "disableCache": false,
  "isAi": false,
  "sseStartTime": 1700000000000,
  "query": "hello",
  "from": "en",
  "to": "zh",
  "corpusIds": [],
  "needPhonetic": true,
  "domain": "common",
  "detectLang": "",
  "isIncognitoAI": false,
  "milliTimestamp": 1700000000000
}
```

主要 SSE 事件：

```text
Start
StartTranslation
Translating
TranslationSucceed
```

译文位于：

```text
data.list[*].dst
```

## 项目结构

```text
.
├─ baidu_web_translate.py          # 主程序
├─ README.md                       # 项目说明
├─ requirements.txt               # Python依赖
├─ package.json                    # Node分析工具配置
├─ package-lock.json               # Node依赖版本锁
├─ ANALYSIS.generated.md           # 自动生成的静态扫描摘要
│
├─ captured/
│  ├─ request-template.json        # 脱敏请求模板
│  ├─ assets-manifest.json         # 原始资源URL、大小和SHA-256
│  ├─ scan-report.json             # 详细关键词及模块扫描结果
│  ├─ har-analysis.sanitized.json  # 脱敏后的HAR分析结果
│  ├─ original/                    # 下载的网页HTML和原始JS
│  └─ formatted/                   # 格式化后的主JS
│
├─ js/
│  ├─ extracted/
│  │  └─ translate_request.mjs     # 提取后的业务层JS
│  ├─ hooks/
│  │  └─ devtools_hook.js          # 手动粘贴到Console的脱敏Hook
│  ├─ analyze_ast.mjs              # Babel AST分析
│  ├─ format_target.mjs            # Prettier格式化
│  └─ test_extracted.mjs           # JS逻辑测试
│
├─ scripts/
│  ├─ download_assets.py           # 下载当前页面和关键JS
│  ├─ scan_bundles.py              # 搜索接口、ACS和webpack模块
│  └─ parse_har.py                 # 提取并脱敏HAR请求
│
└─ tests/
   └─ test_python_logic.py         # Python单元测试
```

## 逆向分析工具

### 更新网页和原始 JavaScript

```powershell
python .\scripts\download_assets.py
```

脚本会从当前 HTML 动态发现主包文件名，并记录每个文件的 URL、大小、SHA-256 和 Source Map 探测结果。

### 重新扫描关键字符串和模块

```powershell
python .\scripts\scan_bundles.py
```

主要扫描：

```text
/ait/text/translate
milliTimestamp
useAcsToken
Acs-Token
getAcsInstance
getSign
svcp_stk
TranslationSucceed
```

### 格式化压缩主包

```powershell
npm.cmd run format -- `
  captured/original/index.xxxxxxxx.js `
  captured/formatted/index.formatted.js
```

### AST 分析

```powershell
npm.cmd run ast -- captured/original/index.xxxxxxxx.js
```

### 解析并脱敏 HAR

```powershell
python .\scripts\parse_har.py `
  "D:\path\baidu-success.har" `
  -o ".\captured\har-analysis.sanitized.json"
```

脱敏工具会隐藏：

- `Cookie`
- `Set-Cookie`
- `Authorization`
- 完整 `Acs-Token`

## 运行测试

Python 测试：

```powershell
python -m unittest discover -s tests -v
```

JavaScript 测试：

```powershell
npm.cmd test
```

当前测试覆盖：

- Payload字段和时间戳
- HAR中成功请求的识别
- `Acs-Token` Header加载
- SSE事件解析
- 译文拼接
- `995/1022` 风控错误处理
- ACS外层回调的Promise封装

## 常见问题

### `the following arguments are required: texts`

运行程序时没有提供待翻译文本。正确写法：

```powershell
python .\baidu_web_translate.py "hello"
```

### `can't open file ... baidu_web_translate.py`

当前终端不在项目目录。先进入项目：

```powershell
cd "项目所在目录\百度翻译JS逆向"
python .\baidu_web_translate.py "hello"
```

也可以直接使用主程序的完整路径。

### `errno=995, request is not authorized`

当前请求缺少有效 ACS 上下文，或者 HAR 中的 Token 已过期。重新在网页中完成一次成功翻译并导出 HAR。

### HTTP状态是200，为什么仍然失败？

该接口使用 SSE。HTTP 200 只代表连接成功，业务错误仍可能出现在后续 `data:` 事件中，因此程序还会检查 `errno`。

### 为什么不直接提供固定的 `sign.js`？

当前版本不是旧教程中的固定 `token + sign`。主包调用动态加载的 Paris/ACS SDK，Token可能与时间、浏览器环境和风控状态关联。项目只复现已经确认的业务层调用和自己成功请求的短期上下文，不伪造 ACS 内部环境。

### 能否长期稳定运行？

不能保证。以下变化都可能导致失效：

- ACS Token过期
- 网页Payload字段变化
- 接口路径变化
- webpack模块重新打包
- 风控开始强制绑定Cookie、环境或验证码

长期稳定翻译应使用百度官方开放平台；本项目重点是逆向分析过程。

## 更新与维护流程

网站升级后建议按以下顺序检查：

```text
1. 浏览器确认网页本身仍能翻译
2. 重新导出一条成功HAR
3. 运行download_assets.py下载当前JS
4. 运行scan_bundles.py生成新扫描报告
5. 对比接口、Payload和ACS调用链
6. 更新主程序
7. 运行Python和Node测试
```

## 免责声明

本仓库仅用于技术学习、代码调试和研究网页前端请求结构。使用者应遵守目标网站的服务条款、robots规则、访问频率限制以及所在地法律法规。由不当使用造成的账号限制、访问封禁或其他后果，由使用者自行承担。

