/**
 * Landing page — placeholder for the Smart Meat MVP.
 *
 * This page will redirect authenticated users to the dashboard once the auth
 * flow is implemented in WU-3.
 */

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-50 p-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900">Smart Meat</h1>
        <p className="mt-4 text-lg text-gray-600">
          AI-powered meat procurement platform
        </p>
        <p className="mt-2 text-sm text-gray-400">
          Dashboard coming soon — sign in to get started.
        </p>
      </div>
    </main>
  );
}
