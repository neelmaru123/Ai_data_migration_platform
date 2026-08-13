import './globals.css';
import StoreProvider from '../providers/StoreProvider';

export const metadata = {
  title: 'AI Data Migration Platform',
  description: 'Enterprise AI-powered schema translation & data migration tool',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 min-h-screen antialiased">
        <StoreProvider>{children}</StoreProvider>
      </body>
    </html>
  );
}

