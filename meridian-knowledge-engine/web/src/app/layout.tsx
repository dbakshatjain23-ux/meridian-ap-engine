import type { Metadata } from 'next';
import { Inter, Hanken_Grotesk, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });
const hanken = Hanken_Grotesk({ subsets: ['latin'], variable: '--font-hanken' });
const jetbrains = JetBrains_Mono({ subsets: ['latin'], variable: '--font-jetbrains' });

export const metadata: Metadata = {
  title: 'Meridian Knowledge Engine',
  description: 'Generic Dual-Clock Temporal Knowledge Engine + Industry Plug-ins',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${hanken.variable} ${jetbrains.variable}`}>
      <body className={`${inter.className} ${hanken.className} ${jetbrains.className} antialiased`}>
        {children}
      </body>
    </html>
  );
}