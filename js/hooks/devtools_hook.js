/**
 * 手动粘贴到百度翻译页面的DevTools Console中执行。
 * 功能：记录目标fetch/XHR的URL、方法、脱敏请求头和请求体。
 * 不自动点击、不发送额外请求、不输出完整Cookie或Acs-Token。
 */
(() => {
  "use strict";

  const TARGET = "/ait/text/translate";
  const SENSITIVE = new Set(["acs-token", "cookie", "authorization"]);

  function redactHeaders(input) {
    const output = {};
    if (!input) return output;

    const headers = new Headers(input);
    for (const [name, value] of headers.entries()) {
      output[name] = SENSITIVE.has(name.toLowerCase())
        ? `<redacted length=${value.length}>`
        : value;
    }
    return output;
  }

  function show(label, detail) {
    console.groupCollapsed(`[百度翻译逆向] ${label}`);
    console.log(detail);
    console.trace("调用栈");
    console.groupEnd();
  }

  const originalFetch = window.fetch;
  window.fetch = function hookedFetch(input, init = {}) {
    const url = typeof input === "string" ? input : input.url;
    if (url.includes(TARGET)) {
      const requestHeaders = init.headers ??
        (typeof input === "object" ? input.headers : undefined);
      show("fetch", {
        url,
        method: init.method ?? (input.method || "GET"),
        headers: redactHeaders(requestHeaders),
        body: init.body ?? "<body位于Request对象中>",
      });
    }
    return originalFetch.apply(this, arguments);
  };

  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSetHeader = XMLHttpRequest.prototype.setRequestHeader;
  const originalSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function hookedOpen(method, url) {
    this.__reverseInfo = { method, url: String(url), headers: {} };
    return originalOpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.setRequestHeader = function hookedSetHeader(name, value) {
    if (this.__reverseInfo) this.__reverseInfo.headers[name] = value;
    return originalSetHeader.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function hookedSend(body) {
    if (this.__reverseInfo?.url.includes(TARGET)) {
      show("XMLHttpRequest", {
        ...this.__reverseInfo,
        headers: redactHeaders(this.__reverseInfo.headers),
        body,
      });
    }
    return originalSend.apply(this, arguments);
  };

  window.__BAIDU_REVERSE_UNHOOK__ = () => {
    window.fetch = originalFetch;
    XMLHttpRequest.prototype.open = originalOpen;
    XMLHttpRequest.prototype.setRequestHeader = originalSetHeader;
    XMLHttpRequest.prototype.send = originalSend;
    delete window.__BAIDU_REVERSE_UNHOOK__;
    console.log("百度翻译逆向Hook已移除");
  };

  console.log("百度翻译逆向Hook已安装；调用 __BAIDU_REVERSE_UNHOOK__() 可恢复");
})();

