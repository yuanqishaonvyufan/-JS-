import assert from "node:assert/strict";
import {
  addAcsHeader,
  buildRequestInit,
  buildTranslatePayload,
  collectTranslation,
  parseSSELines,
} from "./extracted/translate_request.mjs";

const payload = buildTranslatePayload({
  query: " hello ",
  now: () => 1700000000123,
});

assert.deepEqual(payload, {
  needNewlineCombine: false,
  disableCache: false,
  isAi: false,
  sseStartTime: 1700000000123,
  query: "hello",
  from: "en",
  to: "zh",
  corpusIds: [],
  needPhonetic: true,
  domain: "common",
  detectLang: "",
  isIncognitoAI: false,
  milliTimestamp: 1700000000123,
});

const request = buildRequestInit(payload, { acsToken: "test-token" });
assert.equal(request.method, "POST");
assert.equal(request.credentials, "include");
assert.equal(request.headers["Acs-Token"], "test-token");
assert.equal(JSON.parse(request.body).query, "hello");

// 用Mock证明“主包外层包装”可运行，但不伪造ACS内部算法。
const headers = await addAcsHeader(
  { "Content-Type": "application/json" },
  (callback) => callback(null, "mock-acs-token"),
);
assert.equal(headers["Acs-Token"], "mock-acs-token");

const sseLines = [
  "event: message",
  'data: {"errno":0,"data":{"event":"StartTranslation"}}',
  "",
  "event: message",
  'data: {"errno":0,"data":{"event":"Translating","list":[{"id":1,"src":"hello","dst":"你好"}]}}',
  "",
  "event: message",
  'data: {"errno":0,"data":{"event":"TranslationSucceed"}}',
  "",
];

assert.equal(collectTranslation(parseSSELines(sseLines)), "你好");
console.log("JS提取逻辑测试通过");
