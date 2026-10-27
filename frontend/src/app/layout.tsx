import type { Metadata, Viewport } from 'next';
import Link from 'next/link';
import { DM_Mono, Manrope, Space_Grotesk } from 'next/font/google';
import SceneShell from '@/components/SceneShell';
import ThemeSwitcher from '@/components/ThemeSwitcher';
import GatewayStatus from '@/components/dashboard/GatewayStatus';
import Providers from '@/components/Providers';
import { DEFAULT_THEME, themeBootScript, themesCss } from '@/lib/themes';
import './globals.css';

const display = Space_Grotesk({ subsets: ['latin'], variable: '--font-display', display: 'swap' });
const body = Manrope({ subsets: ['latin'], variable: '--font-body', display: 'swap' });
const mono = DM_Mono({ subsets: ['latin'], weight: ['400', '500'], variable: '--font-mono', display: 'swap' });

export const metadata: Metadata = {
  title: 'AI Security Router',
  description: 'One plug-and-play security gateway in front of any app or LLM: learned detector routing, policy engine, red-team loop.',
};
export const viewport: Viewport = { themeColor: '#000000' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // data-theme is rewritten by the boot script before paint -> suppress the expected attribute mismatch
    <html lang="en" data-theme={DEFAULT_THEME} suppressHydrationWarning className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <head>
        <style dangerouslySetInnerHTML={{ __html: themesCss() }} />
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body>
        <Providers>
          <SceneShell />
          <header className="site-header">
            <Link className="brand" href="/">AI Security Router<span>.</span></Link>
            <nav aria-label="Main">
              <Link href="#live">Live</Link>
              <Link href="#console">Console</Link>
              <Link href="#chat">Chat</Link>
              <Link href="#audit">Audit</Link>
              <Link href="#redteam">Red team</Link>
            </nav>
            <div className="header-end">
              <GatewayStatus />
              <ThemeSwitcher />
            </div>
          </header>
          <main className="page">{children}</main>
          <footer className="site-footer">
            <span>AI Security Router — learned routing · policy · red-team</span>
            <span className="mono-muted">FastAPI + Next.js + R3F · local demo</span>
          </footer>
        </Providers>
      </body>
    </html>
  );
}
