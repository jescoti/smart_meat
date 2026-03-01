"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { fetchCurrentUser } from "@/lib/auth";
import { useAuthStore } from "@/stores/authStore";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  const setUser = useAuthStore((s) => s.setUser);
  const setLoading = useAuthStore((s) => s.setLoading);

  useEffect(() => {
    fetchCurrentUser().then((user) => {
      if (user) {
        setUser(user);
      }
      setLoading(false);
    });
  }, [setUser, setLoading]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
