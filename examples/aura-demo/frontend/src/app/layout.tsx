import "./globals.css";
import { AppShell } from "@/components/AppShell";
import { AuthProvider } from "@/components/auth/AuthContext";

export const metadata = { title: "ASSURE — Portfolio Assurance" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-aura-background text-aura-text antialiased">
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
