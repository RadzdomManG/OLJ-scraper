import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'Aurelius | Job Intelligence Portal', description: 'Your live job intelligence workspace' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
