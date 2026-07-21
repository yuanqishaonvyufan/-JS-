/**
 * 从百度当前主包中还原出的“业务层最小逻辑”。
 *
 * 这里刻意没有伪造 ACS 算法：主包只负责调用 Paris SDK 的 getSign()，
 * 真正的风控实现位于动态加载的混淆脚本，并依赖浏览器环境。
 */

export const PAGE_URL = "https://fanyi.baidu.com/mtpe-individual/transText";
export const API_URL = "https://fanyi.baidu.com/ait/text/translate";
export const ACS_SID = "2060";

/** 对应前端在发送前执行 {...payload, milliTimestamp: Date.now()}。 */
export function buildTranslatePayload({
  query,
  from = "en",
  to = "zh",
  corpusIds = [],
  needPhonetic = true,
  domain = "common",
  now = Date.now,
}) {
  if (typeof query !== "string" || query.trim() === "") {
    throw new TypeError("query必须是非空字符串");
  }

  const nowMs = now();
  return {
    needNewlineCombine: false,
    disableCache: false,
    isAi: false,
    sseStartTime: nowMs,
    query: query.trim(),
    from,
    to,
    corpusIds,
    needPhonetic,
    domain,
    detectLang: "",
    isIncognitoAI: false,
    milliTimestamp: nowMs,
  };
}

/** 生成与DevTools中结构一致的fetch参数。 */
export function buildRequestInit(payload, { acsToken } = {}) {
  const headers = {
    Accept: "text/event-stream",
    "Content-Type": "application/json",
  };

  if (acsToken) {
    headers["Acs-Token"] = acsToken;
  }

  return {
    method: "POST",
    credentials: "include",
    headers,
    body: JSON.stringify(payload),
  };
}

/**
 * 主包模块88172的外层行为：把回调式getSign包装成Promise。
 * getSign由Paris/ACS SDK提供，本函数不实现其内部风控算法。
 */
export function callParisGetSign(getSign) {
  if (typeof getSign !== "function") {
    return Promise.reject(new TypeError("getSign必须是函数"));
  }

  return new Promise((resolve, reject) => {
    getSign((error, token) => {
      if (error) {
        reject(error);
        return;
      }
      resolve(token);
    });
  });
}

/** 对应主包把SDK返回值合并为 Acs-Token 请求头。 */
export async function addAcsHeader(headers, getSign) {
  const token = await callParisGetSign(getSign);
  return { ...headers, "Acs-Token": token };
}

/** 把一组SSE文本行解析为data中的JSON消息。 */
export function parseSSELines(lines) {
  const messages = [];
  let dataLines = [];

  const flush = () => {
    if (dataLines.length === 0) return;
    messages.push(JSON.parse(dataLines.join("\n")));
    dataLines = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.replace(/\r$/, "");
    if (line === "") {
      flush();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  flush();
  return messages;
}

/** 从Translating事件中按id收集译文。 */
export function collectTranslation(messages) {
  const parts = new Map();

  for (const message of messages) {
    if (message?.errno && message.errno !== 0) {
      throw new Error(`百度接口错误：${message.errno} ${message.errmsg ?? ""}`);
    }

    const data = message?.data ?? {};
    if (data.event !== "Translating") continue;

    for (const [index, item] of (data.list ?? []).entries()) {
      parts.set(String(item.id ?? index), item.dst ?? "");
    }
  }

  return [...parts.values()].join("");
}
