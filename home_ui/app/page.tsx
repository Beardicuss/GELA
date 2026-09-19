"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";

// Dynamic imports with ssr: false completely avoid hydration mismatches
const HexWorld = dynamic(() => import("@/components/ApexWorld"), { ssr: false });
const HexOverviewPanel = dynamic(() => import("@/components/ApexOverviewPanel"), { ssr: false });

export default function Home() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <main
        id="main"
        suppressHydrationWarning
        style={{
          background: "#0e0b0b",
          color: "#f0ede8",
          position: "relative",
          overflow: "hidden",
          width: "100vw",
          height: "100vh",
        }}
      />
    );
  }

  return (
    <main
      id="main"
      suppressHydrationWarning
      style={{
          background: "#0e0b0b",
        color: "#f0ede8",
        position: "relative",
        overflow: "hidden",
        width: "100vw",
        height: "100vh",
      }}
    >
      {/* Top-left overview HUD */}
      <HexOverviewPanel />

      {/* Gela's avatar or orb and its PC controls */}
      <section style={{ position: "relative", height: "100vh", minHeight: 620 }}>
        <HexWorld />
      </section>
    </main>
  );
}
