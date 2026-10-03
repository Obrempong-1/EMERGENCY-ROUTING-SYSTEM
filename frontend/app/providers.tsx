"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import ActingBanner from "../components/ActingBanner";

export default function Providers({ children }: { children: React.ReactNode }) {
    const [client] = useState(() => new QueryClient({
        defaultOptions: {
            queries: {
                staleTime: 5 * 60_000,
                gcTime: 30 * 60_000,
                retry: 1,
                refetchOnWindowFocus: false,
            },
        },
    }));

    return (
        <QueryClientProvider client={client}>
            {children}
            <ActingBanner />
        </QueryClientProvider>
    );
}
