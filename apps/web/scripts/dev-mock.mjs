// 백엔드 없이 목 API로 Next 개발 서버를 실행합니다 (Windows/macOS 공통).
import { spawn } from "node:child_process";

const child = spawn(
  "next",
  ["dev", "--hostname", "127.0.0.1", ...process.argv.slice(2)],
  {
    stdio: "inherit",
    shell: true,
    env: { ...process.env, NEXT_PUBLIC_API_MOCK: "1" },
  },
);
child.on("exit", (code) => process.exit(code ?? 0));
