import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Rule_U · 보드게임 규칙 도우미",
  description: "게임의 규칙을 묻고, 근거를 확인하는 공간",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
