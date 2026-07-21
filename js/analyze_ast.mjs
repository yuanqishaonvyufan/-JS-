import fs from "node:fs";
import path from "node:path";
import { parse } from "@babel/parser";
import traverseModule from "@babel/traverse";

const input = process.argv[2];
if (!input) {
  console.error("用法：node js/analyze_ast.mjs <目标JS文件>");
  process.exit(2);
}

const code = fs.readFileSync(input, "utf8");
const ast = parse(code, {
  sourceType: "unambiguous",
  errorRecovery: true,
  allowReturnOutsideFunction: true,
});

const traverse = traverseModule.default ?? traverseModule;
const patterns = [
  "/ait/text/translate",
  "Acs-Token",
  "useAcsToken",
  "getAcsInstance",
  "getSign",
  "milliTimestamp",
  "svcp_stk",
];
const hits = [];

function record(pathRef, value) {
  if (!patterns.some((pattern) => String(value).includes(pattern))) return;
  hits.push({
    type: pathRef.node.type,
    value,
    line: pathRef.node.loc?.start.line ?? null,
    column: pathRef.node.loc?.start.column ?? null,
  });
}

traverse(ast, {
  StringLiteral(pathRef) {
    record(pathRef, pathRef.node.value);
  },
  Identifier(pathRef) {
    record(pathRef, pathRef.node.name);
  },
});

const output = {
  file: path.resolve(input),
  bytes: Buffer.byteLength(code),
  parserErrors: ast.errors?.map((error) => error.message) ?? [],
  hits,
};

console.log(JSON.stringify(output, null, 2));

