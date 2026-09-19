"use client";

import React, { useRef, useMemo, useState, useEffect, Suspense } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshSurfaceSampler } from "three/examples/jsm/math/MeshSurfaceSampler.js";
import type { OrbState } from "./ApexHeroOrb";

/* ─── Error Boundary ─────────────────────────────────────── */
class AvatarErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; message: string }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, message: "" };
  }
  static getDerivedStateFromError(e: Error) { return { hasError: true, message: e.message }; }
  componentDidCatch(e: Error, info: React.ErrorInfo) {
    console.error("[Avatar3D] ErrorBoundary caught:", e.message, info.componentStack);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", color: "#dc5148", fontFamily: "monospace", fontSize: 11 }}>
          [AVATAR ERROR: {this.state.message}]
        </div>
      );
    }
    return this.props.children;
  }
}

/* ─── Glow sprite ─────────────────────────────────────────── */
function makeSprite(): THREE.Texture {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0,    "rgba(255,255,255,1)");
  g.addColorStop(0.18, "rgba(255,210,194,0.9)");
  g.addColorStop(0.5,  "rgba(220,81,72,0.35)");
  g.addColorStop(1,    "rgba(0,0,0,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c);
  t.needsUpdate = true;
  return t;
}

/* ─── Shaders ─────────────────────────────────────────────── */
const vert = /* glsl */`
  uniform float uTime;
  uniform float uState;
  uniform float uVoice;
  attribute vec3 aNorm;
  attribute vec3 aCol;
  attribute float aPhase;
  attribute float aSpeed;
  varying vec3 vCol;
  varying float vAlpha;

  void main() {
    vCol = aCol;
    vec3 p = position;
    float ph = aPhase;
    float t  = uTime * aSpeed;

    // ── Cull interior-facing particles (mouth cavity, eye sockets) ──
    // normalMatrix transforms model normals into view space.
    // Interior surfaces face AWAY from camera → negative view-space Z.
    vec3 viewN = normalize(normalMatrix * aNorm);
    if (viewN.z < -0.3) {
      gl_Position = vec4(10.0, 10.0, 10.0, 1.0); // push off-screen
      gl_PointSize = 0.0;
      vAlpha = 0.0;
      return;
    }

    // Idle: gentle surface breathing
    float breath = sin(uTime * 1.4 + p.y * 2.5 + ph) * 0.007;
    p += aNorm * breath;

    // Thinking: outward dispersion + neural swirl + gold sparks
    if (uState > 0.1) {
      float strength = smoothstep(0.1, 1.0, uState) * (1.0 - smoothstep(1.0, 2.0, uState));
      float d = strength * (0.03 + sin(uTime * 3.0 + ph) * 0.025);
      p += aNorm * d;
      float sw = strength * sin(uTime * 2.2 + p.y * 3.5) * 0.015;
      p.x += cos(p.z * 4.0 + t) * sw;
      p.z += sin(p.x * 4.0 + t) * sw;
      if (sin(ph * 7.3 + uTime * 5.0) > 0.5) {
        vCol = mix(vCol, vec3(1.0, 0.65, 0.4), strength * 0.8);
      }
    }

    // Speaking: whole-surface ripple wave + subtle ice tint
    if (uState > 1.1) {
      float strength = smoothstep(1.1, 2.0, uState);
      float wave = sin(p.y * 12.0 - uTime * 14.0 + ph) * 0.012 * strength;
      p += aNorm * wave;
      float lowFace = smoothstep(0.0, -0.15, p.y);
      p += aNorm * lowFace * sin(uTime * 18.0 + ph) * uVoice * 0.03;
      vCol = mix(vCol, vec3(1.0, 0.78, 0.7), strength * 0.25);
    }

    vec4 mvp = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mvp;
    gl_PointSize = max(1.0, 5.0 / -mvp.z);
    vAlpha = 0.9;
  }
`;

const frag = /* glsl */`
  uniform sampler2D uTex;
  varying vec3 vCol;
  varying float vAlpha;
  void main() {
    float a = texture2D(uTex, gl_PointCoord).a;
    if (a < 0.04) discard;
    gl_FragColor = vec4(vCol, vAlpha * a);
  }
`;

/* ─── Sample mesh surface ─────────────────────────────────── */
const PARTICLE_COUNT = 70_000;

function buildParticleCloud(mesh: THREE.Mesh) {
  const sampler = new MeshSurfaceSampler(mesh).build();
  const pos    = new Float32Array(PARTICLE_COUNT * 3);
  const norms  = new Float32Array(PARTICLE_COUNT * 3);
  const cols   = new Float32Array(PARTICLE_COUNT * 3);
  const phases = new Float32Array(PARTICLE_COUNT);
  const speeds = new Float32Array(PARTICLE_COUNT);

  const p = new THREE.Vector3();
  const n = new THREE.Vector3();

  // Gela red 60%, pale rose 25%, warm copper 15%.
  const palette: [number,number,number][] = [
    [0.86, 0.27, 0.24],
    [1.0, 0.71, 0.65],
    [0.65, 0.14, 0.15],
    [0.87, 0.50, 0.34],
    [1.0, 0.84, 0.73],
  ];
  const cumW = [0.38, 0.60, 0.84, 0.94, 1.0];

  for (let i = 0; i < PARTICLE_COUNT; i++) {
    sampler.sample(p, n);
    pos[i*3]     = p.x; pos[i*3+1]   = p.y; pos[i*3+2]   = p.z;
    norms[i*3]   = n.x; norms[i*3+1] = n.y; norms[i*3+2] = n.z;
    const r = Math.random();
    const ci = cumW.findIndex(w => r < w);
    const c = palette[ci < 0 ? 0 : ci];
    cols[i*3] = c[0]; cols[i*3+1] = c[1]; cols[i*3+2] = c[2];
    phases[i] = Math.random() * Math.PI * 2;
    speeds[i]  = 0.55 + Math.random() * 0.9;
  }
  return { pos, norms, cols, phases, speeds };
}

/* ─── The R3F scene inner component ─────────────────────────  */
function HeadScene({
  state,
  geo,
  sprite,
  autoScale,
}: {
  state: OrbState;
  geo: THREE.BufferGeometry;
  sprite: THREE.Texture;
  autoScale: number;
}) {
  const groupRef = useRef<THREE.Group>(null);

  const mat = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      uTime:  { value: 0 },
      uState: { value: 0 },
      uVoice: { value: 0 },
      uTex:   { value: sprite },
    },
    vertexShader:   vert,
    fragmentShader: frag,
    transparent: true,
    depthWrite:  false,
    blending:    THREE.AdditiveBlending,
  }), [sprite]);

  const stateTarget = state === "thinking" || state === "listening" ? 1 : state === "speaking" ? 2 : 0;

  useFrame((root, dt) => {
    mat.uniforms.uTime.value  += dt;
    mat.uniforms.uState.value  = THREE.MathUtils.lerp(mat.uniforms.uState.value, stateTarget, 0.1);
    mat.uniforms.uVoice.value  = state === "speaking"
      ? Math.abs(Math.sin(root.clock.elapsedTime * 10)) * 0.4
      : 0;

    if (groupRef.current) {
      const ty = root.pointer.x *  0.45;
      const tx = root.pointer.y * -0.30;
      const tz = root.pointer.x * -0.05;
      groupRef.current.rotation.y = THREE.MathUtils.damp(groupRef.current.rotation.y, ty, 4, dt);
      groupRef.current.rotation.x = THREE.MathUtils.damp(groupRef.current.rotation.x, tx, 4, dt);
      groupRef.current.rotation.z = THREE.MathUtils.damp(groupRef.current.rotation.z, tz, 4, dt);
      groupRef.current.position.y = Math.sin(root.clock.elapsedTime * 1.1) * 0.04 - 0.15;
    }
  });

  return (
    <group ref={groupRef} scale={[autoScale, autoScale, autoScale]}>
      <points geometry={geo} material={mat} />
    </group>
  );
}

function FrameScheduler({ fps }: { fps: number }) {
  const invalidate = useThree((state) => state.invalidate);
  useEffect(() => {
    invalidate();
    if (fps <= 0) return;
    const timer = window.setInterval(invalidate, Math.max(16, Math.round(1000 / fps)));
    return () => window.clearInterval(timer);
  }, [fps, invalidate]);
  return null;
}

/* ─── Public component ────────────────────────────────────── */
export default function ApexHumanoidAvatar3D({
  state: controlled,
  onStateChange,
  interactive = true,
  maxFps = 60,
}: {
  state?: OrbState;
  onStateChange?: (s: OrbState) => void;
  interactive?: boolean;
  maxFps?: number;
}) {
  const [inner, setInner] = useState<OrbState>("idle");
  const state = controlled ?? inner;
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Geo + sprite live in state so they survive across renders
  const [geo, setGeo] = useState<THREE.BufferGeometry | null>(null);
  const [autoScale, setAutoScale] = useState<number>(1.0);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const sprite = useMemo(() => (typeof window !== "undefined" ? makeSprite() : new THREE.Texture()), []);

  // Load GLB imperatively — no Suspense, full error control
  useEffect(() => {
    const loader = new GLTFLoader();
    console.log("[Avatar3D] Starting GLB load from /models/head.glb");

    loader.load(
      "/models/head.glb",
      (gltf) => {
        console.log("[Avatar3D] GLB loaded OK. Scene children:", gltf.scene.children.length);
        let mesh: THREE.Mesh | null = null;
        gltf.scene.traverse(obj => {
          if (!mesh && (obj as THREE.Mesh).isMesh) {
            mesh = obj as THREE.Mesh;
            console.log("[Avatar3D] Mesh found:", mesh.name, "verts:", mesh.geometry.attributes.position?.count);
          }
        });
        if (!mesh) {
          console.error("[Avatar3D] No mesh inside GLB!");
          setLoadErr("No mesh found in GLB");
          return;
        }
        try {
          // ── Auto-fit: normalise scale so head height ≈ 1.4 world units ──
          // Camera is at z=3.5, fov=50 → visible height at z=0 ≈ 3.3 units.
          // Target: head fills ~42% of that → ~1.4 units tall.
          const box = new THREE.Box3().setFromObject(mesh!);
          const size = new THREE.Vector3();
          box.getSize(size);
          const maxDim = Math.max(size.x, size.y, size.z);
          const targetSize = 1.4;
          const scale = maxDim > 0 ? targetSize / maxDim : 1.0;
          console.log("[Avatar3D] BBox:", size, "→ autoScale:", scale);
          setAutoScale(scale);

          const { pos, norms, cols, phases, speeds } = buildParticleCloud(mesh!);
          const g = new THREE.BufferGeometry();
          g.setAttribute("position", new THREE.BufferAttribute(pos,    3));
          g.setAttribute("aNorm",    new THREE.BufferAttribute(norms,  3));
          g.setAttribute("aCol",     new THREE.BufferAttribute(cols,   3));
          g.setAttribute("aPhase",   new THREE.BufferAttribute(phases, 1));
          g.setAttribute("aSpeed",   new THREE.BufferAttribute(speeds, 1));
          console.log("[Avatar3D] Particle cloud built:", PARTICLE_COUNT, "points");
          setGeo(g);
        } catch (e) {
          console.error("[Avatar3D] Sampling error:", e);
          setLoadErr(String(e));
        }
      },
      (xhr) => {
        if (xhr.total > 0) {
          console.log("[Avatar3D] Loading:", Math.round(xhr.loaded / xhr.total * 100) + "%");
        }
      },
      (err) => {
        console.error("[Avatar3D] GLB load failed:", err);
        setLoadErr(String(err));
      }
    );
  }, []);

  const cycle = () => {
    if (!interactive) return;
    const next: OrbState = state === "idle" ? "thinking" : state === "thinking" ? "speaking" : "idle";
    setInner(next);
    onStateChange?.(next);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => { setInner("idle"); onStateChange?.("idle"); }, 8000);
  };

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  return (
    <div
      style={{ position: "absolute", inset: 0, pointerEvents: interactive ? "auto" : "none", cursor: interactive ? "pointer" : "default" }}
      onClick={cycle}
      role="button"
      tabIndex={0}
      aria-label="Gela avatar"
    >
      {loadErr && (
        <div style={{ position: "absolute", bottom: 20, left: "50%", transform: "translateX(-50%)", color: "#ff4444", fontFamily: "monospace", fontSize: 10, zIndex: 10 }}>
          [AVATAR ERR: {loadErr}]
        </div>
      )}

      {geo && (
        <AvatarErrorBoundary>
          <Canvas
            frameloop="demand"
            camera={{ position: [0, 0, 3.5], fov: 50 }}
            dpr={[1, 1.5]}
            gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
            style={{ position: "absolute", inset: 0, background: "transparent", pointerEvents: "none" }}
          >
            <FrameScheduler fps={maxFps} />
            <HeadScene state={state} geo={geo} sprite={sprite} autoScale={autoScale} />
            <EffectComposer multisampling={0}>
              <Bloom
                luminanceThreshold={0.35}
                luminanceSmoothing={0.75}
                intensity={1.4}
                radius={0.6}
                mipmapBlur
              />
            </EffectComposer>
          </Canvas>
        </AvatarErrorBoundary>
      )}

      {!geo && !loadErr && (
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {/* transparent while loading */}
        </div>
      )}
    </div>
  );
}
