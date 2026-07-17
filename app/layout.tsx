import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediaX Agent Bank — Trung tâm vận hành AI",
  description: "Nền tảng điều phối chuyên gia AI cho nghiệp vụ ngân hàng.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="vi"><body>{children}</body></html>;
}
