import "./globals.css";
import { AppShell } from "@/components/AppShell";

export const metadata = { title: "ASSURE — Portfolio Assurance" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-aura-background text-aura-text antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
