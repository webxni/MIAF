import type { Metadata } from "next";
import "./globals.css";
import { brand } from "./_lib/brand";

export const metadata: Metadata = {
  title: brand.displayName,
  description: brand.description,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
        {children}
      </body>
    </html>
  );
}
