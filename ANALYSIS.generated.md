# 百度翻译JS静态扫描报告

> 由 `scripts/scan_bundles.py` 根据当前下载文件生成。位置是字符偏移，不是源码行号。

## `captured/original/abclite-2060-s.js`

- 字符数：191395
- 识别出的webpack模块：0


## `captured/original/acs-2060.js`

- 字符数：226158
- 识别出的webpack模块：0


## `captured/original/index.570f2c7a.js`

- 字符数：5358915
- 识别出的webpack模块：908

- `/ait/text/translate`：4处；模块：35353, 71890
- `milliTimestamp`：5处；模块：25880, 35353, 50978
- `useAcsToken`：12处；模块：25880, 35353, 83276, 87878
- `Acs-Token`：3处；模块：50978, 88172
- `getAcsInstance`：1处；模块：88172
- `getSign`：1处；模块：88172
- `paris_`：1处；模块：88172
- `abclite-`：2处；模块：88172
- `acs-`：2处；模块：88172
- `svcp_stk`：1处；模块：71890
- `TranslationSucceed`：2处；模块：25880, 35353
- `Translating`：3处；模块：25880, 35353

## `captured/original/runtime.692330f3.js`

- 字符数：6662
- 识别出的webpack模块：0


## `captured/original/uni_login_wrapper.js`

- 字符数：8634
- 识别出的webpack模块：0


## `captured/original/vendors.5568ef9a.js`

- 字符数：4567063
- 识别出的webpack模块：0

- `getAcsInstance`：2处；模块：未识别
- `getSign`：2处；模块：未识别
- `paris_`：1处；模块：未识别
- `acs-`：1处；模块：未识别

## 已确认的业务调用链

```text
35353（翻译SSE）
  → 83276（SSE请求封装）
  → 88172（Paris/ACS外层封装）
  → Acs-Token请求头

71890（命中风险时调起验证码并写svcp_stk）
```

完整上下文位于 `captured/scan-report.json`。
