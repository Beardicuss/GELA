/**
 * Refined Cybernetic 3D Humanoid Face Generator
 * Produces an elegant, sculpted holographic face point cloud with distinct
 * facial contours: brows, eyelids, nose ridge, sculpted lips, jawline,
 * cheekbones, and cranial neural circuits.
 */

export interface ParticleCloudData {
  positions: Float32Array;
  normals: Float32Array;
  colors: Float32Array;
  regions: Float32Array; // 0: cranium/neural, 1: contours/cheeks, 2: eyes/brows, 3: mouth/jaw, 4: neck/throat, 5: aura
  phases: Float32Array;
  speeds: Float32Array;
  count: number;
}

export function generateHumanoidParticleCloud(): ParticleCloudData {
  const positions: number[] = [];
  const normals: number[] = [];
  const colors: number[] = [];
  const regions: number[] = [];
  const phases: number[] = [];
  const speeds: number[] = [];

  const push = (
    x: number,
    y: number,
    z: number,
    nx: number,
    ny: number,
    nz: number,
    rgb: [number, number, number],
    region: number,
    speed = 1.0
  ) => {
    const len = Math.hypot(nx, ny, nz) || 1;
    positions.push(x, y, z);
    normals.push(nx / len, ny / len, nz / len);
    colors.push(rgb[0], rgb[1], rgb[2]);
    regions.push(region);
    phases.push(Math.random() * Math.PI * 2);
    speeds.push(speed);
  };

  // Color Palette
  const CYAN: [number, number, number] = [0.0, 0.9, 1.0];         // #00e5ff
  const ICE: [number, number, number] = [0.75, 0.95, 1.0];        // #c0f2ff
  const DEEP_CYAN: [number, number, number] = [0.04, 0.55, 0.85]; // #0aa
  const GOLD: [number, number, number] = [0.98, 0.68, 0.15];      // #faa626
  const PALE_GOLD: [number, number, number] = [1.0, 0.85, 0.55];

  // ── 1. EYES (Defined almond contours + pupil motes) ──
  const eyeCenterX = 0.28;
  const eyeCenterY = 0.26;
  const eyeCenterZ = 0.54;

  for (const side of [-1, 1]) {
    const cx = side * eyeCenterX;

    // Pupil core
    push(cx, eyeCenterY, eyeCenterZ + 0.04, 0, 0, 1, ICE, 2, 1.6);
    push(cx + 0.015, eyeCenterY, eyeCenterZ + 0.04, 0, 0, 1, ICE, 2, 1.5);
    push(cx - 0.015, eyeCenterY, eyeCenterZ + 0.04, 0, 0, 1, ICE, 2, 1.5);

    // Eyelid contour points (almond shape)
    const eyePoints = 70;
    for (let i = 0; i < eyePoints; i++) {
      const angle = (i / eyePoints) * Math.PI * 2;
      const rx = 0.11;
      const ry = 0.055;
      const ex = cx + Math.cos(angle) * rx;
      // upper lid arches higher
      const lidBias = Math.sin(angle) > 0 ? 1.2 : 0.8;
      const ey = eyeCenterY + Math.sin(angle) * ry * lidBias;
      const ez = eyeCenterZ + Math.cos(angle) * 0.02;

      push(ex, ey, ez, (ex - cx) * 2, (ey - eyeCenterY) * 2, 1.0, CYAN, 2, 1.3);
    }
  }

  // ── 2. EYEBROWS (Sculpted, sleek arcs) ──
  for (const side of [-1, 1]) {
    const browPoints = 65;
    for (let i = 0; i < browPoints; i++) {
      const t = i / (browPoints - 1); // 0 (inner brow) to 1 (outer arch)
      const bx = side * (0.09 + t * 0.32);
      // Arch curve peaking at t ≈ 0.65
      const arch = Math.sin(t * Math.PI * 0.85) * 0.07;
      const by = 0.36 + arch - t * 0.04;
      const bz = 0.58 - t * 0.14;

      const col = t > 0.6 ? PALE_GOLD : CYAN;
      push(bx, by, bz, side * 0.3, 0.4, 0.9, col, 2, 1.1);
      // Dual line for definition
      push(bx, by + 0.018, bz - 0.01, side * 0.3, 0.5, 0.8, col, 2, 1.0);
    }
  }

  // ── 3. NOSE (Slender nasal bridge, tip, and nostrils) ──
  const noseBridgeSteps = 50;
  for (let i = 0; i < noseBridgeSteps; i++) {
    const t = i / (noseBridgeSteps - 1); // 0 at brow root to 1 at tip
    const ny = 0.34 - t * 0.38;
    const nz = 0.54 + Math.sin(t * Math.PI * 0.65) * 0.18;
    const halfWidth = 0.018 + t * 0.025;

    // Center line
    push(0, ny, nz, 0, 0.1, 1, ICE, 1, 1.0);
    // Lateral edges
    push(-halfWidth, ny, nz - 0.015, -0.8, 0, 0.6, CYAN, 1, 1.0);
    push(halfWidth, ny, nz - 0.015, 0.8, 0, 0.6, CYAN, 1, 1.0);
  }

  // Nostril flares & base
  for (const side of [-1, 1]) {
    for (let i = 0; i < 22; i++) {
      const angle = (i / 22) * Math.PI;
      const nx = side * (0.04 + Math.sin(angle) * 0.045);
      const ny = -0.04 - Math.cos(angle) * 0.025;
      const nz = 0.66 - Math.sin(angle) * 0.04;
      push(nx, ny, nz, side * 0.7, -0.3, 0.6, CYAN, 1, 1.1);
    }
  }

  // ── 4. LIPS & MOUTH (Expressive Cupid's bow, mouth slit, lower lip) ──
  const mouthY = -0.16;
  const mouthZ = 0.62;
  const lipSteps = 80;

  for (let i = 0; i < lipSteps; i++) {
    const t = (i / (lipSteps - 1)) * 2 - 1; // -1 to 1
    const lx = t * 0.22;
    const falloff = 1 - t * t;

    // Cupid's bow on upper lip
    const cupid = Math.sin(Math.abs(t) * Math.PI) * 0.025;
    const upperY = mouthY + 0.035 * falloff + cupid;
    const upperZ = mouthZ + 0.04 * falloff;

    // Fissure (center separation)
    const midY = mouthY - 0.01 * (1 - Math.abs(t));
    const midZ = mouthZ + 0.035 * falloff;

    // Lower lip
    const lowerY = mouthY - 0.05 * falloff;
    const lowerZ = mouthZ + 0.045 * falloff;

    push(lx, upperY, upperZ, lx * 1.5, 0.4, 0.9, ICE, 3, 1.4);
    push(lx, midY, midZ, lx * 1.5, 0.0, 0.9, CYAN, 3, 1.4);
    push(lx, lowerY, lowerZ, lx * 1.5, -0.5, 0.9, CYAN, 3, 1.4);
  }

  // ── 5. JAWLINE & CHIN (Sharp, tapered aerodynamic contour) ──
  for (const side of [-1, 1]) {
    const jawSteps = 90;
    for (let i = 0; i < jawSteps; i++) {
      const t = i / (jawSteps - 1); // 0 at chin to 1 at ear lobe
      // Tapering V-shape
      const jx = side * (0.03 + t * 0.45);
      const jy = -0.36 + t * 0.42;
      const jz = 0.62 - t * 0.65;

      const col = t < 0.25 ? ICE : (t > 0.75 ? GOLD : CYAN);
      push(jx, jy, jz, side * 0.7, -0.4, 0.5 - t * 0.6, col, 3, 1.0);
      // Secondary inner contour for cybernetic depth
      push(jx * 0.94, jy + 0.015, jz + 0.02, side * 0.6, -0.3, 0.6, col, 3, 0.95);
    }
  }

  // Chin prominence
  for (let i = 0; i < 40; i++) {
    const u = (Math.random() - 0.5) * 0.12;
    const v = (Math.random() - 0.5) * 0.07;
    push(u, -0.36 + v, 0.64 - Math.abs(u) * 0.2, 0, -0.5, 0.8, ICE, 3, 1.0);
  }

  // ── 6. CHEEKBONES & TEMPLE CONTOURS (Delicate sculpted arches) ──
  for (const side of [-1, 1]) {
    const cheekSteps = 70;
    for (let i = 0; i < cheekSteps; i++) {
      const t = i / (cheekSteps - 1); // 0 near nose to 1 near ear
      const cx = side * (0.16 + t * 0.34);
      const cy = 0.18 - Math.sin(t * Math.PI) * 0.12;
      const cz = 0.52 - t * 0.42;

      push(cx, cy, cz, side * 0.8, 0.2, 0.6 - t * 0.5, CYAN, 1, 1.0);
      push(cx * 1.04, cy - 0.025, cz - 0.02, side * 0.8, -0.1, 0.5, CYAN, 1, 0.95);
    }
  }

  // ── 7. FOREHEAD & CRANIAL CURVES (Neural longitude / latitude grid) ──
  // Clean spherical contours rather than solid volume
  const latRings = 14;
  for (let r = 0; r < latRings; r++) {
    const lat = 0.1 + (r / latRings) * 0.85; // from brow up to crown
    const y = 0.32 + Math.sin(lat) * 0.62;
    const rad = Math.cos(lat) * 0.55;
    const ringPoints = Math.floor(rad * 140);

    for (let i = 0; i < ringPoints; i++) {
      const theta = (i / ringPoints) * Math.PI * 2;
      const x = Math.sin(theta) * rad * 0.92;
      // Front and top favored
      const z = Math.cos(theta) * rad * 0.95 + 0.08;

      // Only draw if within cranium envelope
      if (z > -0.35 || y > 0.6) {
        const isGoldLine = (r % 3 === 0 && Math.abs(x) < 0.3) || (i % 8 === 0);
        const col = isGoldLine ? GOLD : (Math.random() > 0.4 ? CYAN : DEEP_CYAN);
        push(x, y, z, x, y - 0.3, z, col, 0, 0.85);
      }
    }
  }

  // Longitudinal neural traces flowing over crown
  for (let angleDeg = -70; angleDeg <= 70; angleDeg += 20) {
    const radAng = (angleDeg * Math.PI) / 180;
    const steps = 45;
    for (let s = 0; s < steps; s++) {
      const p = s / (steps - 1);
      const y = 0.42 + Math.sin(p * Math.PI * 0.8) * 0.54;
      const r = 0.52 * Math.cos((p - 0.4) * 1.2);
      const x = Math.sin(radAng) * r;
      const z = Math.cos(radAng) * r * (1 - p * 0.5) + 0.15;

      const col = (s % 5 === 0) ? PALE_GOLD : CYAN;
      push(x, y, z, x, y - 0.2, z, col, 0, 0.9);
    }
  }

  // ── 8. SUBTLE NECK & COLLAR OUTLINE (Fades gracefully down) ──
  const neckRings = 8;
  for (let i = 0; i < neckRings; i++) {
    const t = i / (neckRings - 1);
    const ny = -0.40 - t * 0.26;
    const rad = 0.22 + t * 0.14;
    const ringCount = 28 + Math.floor(t * 16);

    for (let j = 0; j < ringCount; j++) {
      const angle = (j / ringCount) * Math.PI * 2;
      // Open back
      if (Math.sin(angle) > -0.7) {
        const nx = Math.cos(angle) * rad;
        const nz = Math.sin(angle) * rad * 0.85 + 0.1;
        const alphaFade = 1 - t * 0.6;
        const col: [number, number, number] = [CYAN[0] * alphaFade, CYAN[1] * alphaFade, CYAN[2] * alphaFade];
        push(nx, ny, nz, nx, -0.2, nz, col, 4, 0.7);
      }
    }
  }

  // ── 9. AURA & ENERGY HALO MOTES ──
  const moteCount = 350;
  for (let i = 0; i < moteCount; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const rad = 0.95 + Math.random() * 0.55;

    const mx = rad * Math.sin(phi) * Math.cos(theta);
    const my = rad * Math.cos(phi) + 0.15;
    const mz = rad * Math.sin(phi) * Math.sin(theta);

    const isGold = Math.random() < 0.25;
    push(mx, my, mz, mx, my, mz, isGold ? GOLD : CYAN, 5, 0.4);
  }

  return {
    positions: new Float32Array(positions),
    normals: new Float32Array(normals),
    colors: new Float32Array(colors),
    regions: new Float32Array(regions),
    phases: new Float32Array(phases),
    speeds: new Float32Array(speeds),
    count: positions.length / 3,
  };
}
