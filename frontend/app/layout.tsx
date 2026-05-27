import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MoneyMind — An AI co-pilot that remembers who you are.",
  description:
    "A personal finance agent that learns your patterns, holds your context, and acts proactively.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <ClerkProvider
      appearance={{
        variables: {
          colorPrimary: "#34d399",
          colorBackground: "#09090b",
          colorText: "#fafafa",
          colorInputBackground: "#18181b",
          colorInputText: "#fafafa",
          colorNeutral: "#a1a1aa",
        },
      }}
    >
      <html lang="en" className={`${inter.variable} dark h-full`}>
        <body className="min-h-full bg-background text-foreground antialiased">
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
