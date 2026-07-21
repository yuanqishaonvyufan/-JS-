import fs from "node:fs";
import path from "node:path";
import * as prettier from "prettier";

const [input, output] = process.argv.slice(2);
if (!input || !output) {
  console.error("用法：node js/format_target.mjs <输入JS> <输出JS>");
  process.exit(2);
}

const source = fs.readFileSync(input, "utf8");
const formatted = await prettier.format(source, {
  parser: "babel",
  printWidth: 100,
});

fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, formatted, "utf8");
console.log(`已格式化：${input} -> ${output}`);

