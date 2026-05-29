import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "จัดการสินค้า LINE MyShop",
  description: "ระบบจัดการสินค้า รูปภาพ และการส่งขึ้น LINE MyShop",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="th" suppressHydrationWarning>
      <body className="min-h-screen antialiased">
        <header className="sticky top-0 z-20 border-b border-zinc-200/80 bg-white/90 backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
            <Link href="/products" className="flex items-center gap-3">
              <span className="grid h-9 w-9 place-items-center rounded-lg bg-zinc-950 text-sm font-semibold text-white shadow-sm">
                LM
              </span>
              <span>
                <span className="block text-sm font-semibold text-zinc-950">
                  ระบบจัดการสินค้า LINE MyShop
                </span>
                <span className="block text-xs text-zinc-500">ตรวจข้อมูล สร้างรูป และส่งขึ้นร้าน</span>
              </span>
            </Link>
            <nav className="flex gap-2 text-sm">
              <Link
                href="/products"
                className="rounded-md border border-zinc-200 bg-white px-3 py-2 font-medium text-zinc-700 shadow-sm hover:border-zinc-300 hover:bg-zinc-50"
              >
                สินค้า
              </Link>
              <Link
                href="/products/new"
                className="rounded-md border border-zinc-200 bg-white px-3 py-2 font-medium text-zinc-700 shadow-sm hover:border-zinc-300 hover:bg-zinc-50"
              >
                เพิ่มสินค้า
              </Link>
              <Link
                href="/imports"
                className="rounded-md border border-zinc-200 bg-white px-3 py-2 font-medium text-zinc-700 shadow-sm hover:border-zinc-300 hover:bg-zinc-50"
              >
                นำเข้า CSV
              </Link>
              <Link
                href="/sync-jobs"
                className="rounded-md border border-zinc-200 bg-white px-3 py-2 font-medium text-zinc-700 shadow-sm hover:border-zinc-300 hover:bg-zinc-50"
              >
                ประวัติส่ง LINE
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">{children}</main>
      </body>
    </html>
  );
}
