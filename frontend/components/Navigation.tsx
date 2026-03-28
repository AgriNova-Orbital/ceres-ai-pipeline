export default function Navigation() {
  return (
    <nav className="bg-primary text-white px-6 py-3 flex items-center justify-between">
      <span className="font-bold text-lg">Ceres AI Pipeline</span>
      <div className="flex gap-4 text-sm">
        <a href="/" className="hover:underline">Dashboard</a>
        <a href="/api/auth/logout" className="hover:underline">Logout</a>
      </div>
    </nav>
  );
}
