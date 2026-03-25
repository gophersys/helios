<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { getToken } from '$lib/api';
  import ConcordLogo from '$lib/components/concord-logo.svelte';
  import { browser } from '$app/environment';

  const auth = getAuth();

  let error = $state<string | null>(null);
  let loading = $state(false);
  let canvas: HTMLCanvasElement;
  let email = $state('');
  let password = $state('');

  // Redirect if already authenticated (check token directly to avoid timing issues)
  $effect(() => {
    if (auth.isAuthenticated && getToken()) {
      goto('/');
    }
  });

  // Flying planes animation
  interface Plane {
    x: number;
    y: number;
    vx: number;
    vy: number;
    size: number;
    rotation: number;
    trail: { x: number; y: number; alpha: number }[];
  }

  function initPlanesAnimation() {
    if (!browser || !canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;
    const planes: Plane[] = [];
    const numPlanes = 8;

    // Mouse tracking
    let mouseX = -1000;
    let mouseY = -1000;
    let mouseActive = false;
    let mouseTimeout: ReturnType<typeof setTimeout>;

    function onMouseMove(e: MouseEvent) {
      mouseX = e.clientX;
      mouseY = e.clientY;
      mouseActive = true;
      clearTimeout(mouseTimeout);
      mouseTimeout = setTimeout(() => {
        mouseActive = false;
      }, 1500); // Stop following after 1.5s of no movement
    }

    function onMouseLeave() {
      mouseActive = false;
    }

    function resize() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }

    function createPlane(): Plane {
      const angle = Math.random() * Math.PI * 2;
      const speed = 0.8 + Math.random() * 1.2;
      return {
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        size: 8 + Math.random() * 6,
        rotation: angle,
        trail: []
      };
    }

    function drawPlane(plane: Plane) {
      ctx!.save();
      ctx!.translate(plane.x, plane.y);
      ctx!.rotate(plane.rotation + Math.PI); // Flip 180 degrees so nose points forward

      const s = plane.size / 16; // Scale factor (logo is 32x32, centered at 16)
      ctx!.strokeStyle = 'rgba(234, 88, 12, 0.75)'; // Deeper orange
      ctx!.lineWidth = 1.5 * s;
      ctx!.lineCap = 'round';
      ctx!.lineJoin = 'round';

      // Fuselage - same as logo: M3 16L7 13L12 12L26 14.5L30 16L26 17.5L12 20L7 19L3 16Z
      ctx!.beginPath();
      ctx!.moveTo((3 - 16) * s, (16 - 16) * s);
      ctx!.lineTo((7 - 16) * s, (13 - 16) * s);
      ctx!.lineTo((12 - 16) * s, (12 - 16) * s);
      ctx!.lineTo((26 - 16) * s, (14.5 - 16) * s);
      ctx!.lineTo((30 - 16) * s, (16 - 16) * s);
      ctx!.lineTo((26 - 16) * s, (17.5 - 16) * s);
      ctx!.lineTo((12 - 16) * s, (20 - 16) * s);
      ctx!.lineTo((7 - 16) * s, (19 - 16) * s);
      ctx!.closePath();
      ctx!.stroke();

      // Top wing - M14 12L22 6L24 14
      ctx!.beginPath();
      ctx!.moveTo((14 - 16) * s, (12 - 16) * s);
      ctx!.lineTo((22 - 16) * s, (6 - 16) * s);
      ctx!.lineTo((24 - 16) * s, (14 - 16) * s);
      ctx!.stroke();

      // Bottom wing - M14 20L22 26L24 18
      ctx!.beginPath();
      ctx!.moveTo((14 - 16) * s, (20 - 16) * s);
      ctx!.lineTo((22 - 16) * s, (26 - 16) * s);
      ctx!.lineTo((24 - 16) * s, (18 - 16) * s);
      ctx!.stroke();

      // Tail fin - M7 13L11 8
      ctx!.beginPath();
      ctx!.moveTo((7 - 16) * s, (13 - 16) * s);
      ctx!.lineTo((11 - 16) * s, (8 - 16) * s);
      ctx!.stroke();

      ctx!.restore();
    }

    function drawTrail(trail: { x: number; y: number; alpha: number }[]) {
      trail.forEach((dot, i) => {
        const alpha = dot.alpha * 0.5;
        ctx!.beginPath();
        ctx!.arc(dot.x, dot.y, 2 + (i / trail.length) * 2, 0, Math.PI * 2);
        ctx!.fillStyle = `rgba(234, 88, 12, ${alpha})`; // Deeper orange
        ctx!.fill();
      });
    }

    function update() {
      ctx!.clearRect(0, 0, canvas.width, canvas.height);

      planes.forEach(plane => {
        // Add to trail - offset behind the plane based on velocity direction
        const trailOffset = 10; // Distance behind the plane
        const trailX = plane.x - Math.cos(plane.rotation) * trailOffset;
        const trailY = plane.y - Math.sin(plane.rotation) * trailOffset;
        plane.trail.push({ x: trailX, y: trailY, alpha: 0.45 });

        // Limit trail length (longer trail)
        if (plane.trail.length > 45) {
          plane.trail.shift();
        }

        // Fade trail
        plane.trail.forEach(dot => {
          dot.alpha *= 0.96;
        });

        const currentSpeed = Math.sqrt(plane.vx * plane.vx + plane.vy * plane.vy);

        if (mouseActive) {
          // Follow the mouse cursor
          const dx = mouseX - plane.x;
          const dy = mouseY - plane.y;
          const targetAngle = Math.atan2(dy, dx);

          // Smoothly rotate towards target
          let angleDiff = targetAngle - plane.rotation;
          // Normalize angle difference
          while (angleDiff > Math.PI) angleDiff -= Math.PI * 2;
          while (angleDiff < -Math.PI) angleDiff += Math.PI * 2;

          plane.rotation += angleDiff * 0.05; // Smooth turning

          // Speed up slightly when following
          const targetSpeed = Math.min(currentSpeed * 1.02, 2.5);
          plane.vx = Math.cos(plane.rotation) * targetSpeed;
          plane.vy = Math.sin(plane.rotation) * targetSpeed;
        } else {
          // Disperse away from center/mouse position quickly
          const centerX = mouseX > 0 ? mouseX : canvas.width / 2;
          const centerY = mouseY > 0 ? mouseY : canvas.height / 2;
          const dx = plane.x - centerX;
          const dy = plane.y - centerY;
          const distFromCenter = Math.sqrt(dx * dx + dy * dy);

          // If too close to where mouse was, push away
          if (distFromCenter < 300) {
            const awayAngle = Math.atan2(dy, dx);
            let angleDiff = awayAngle - plane.rotation;
            while (angleDiff > Math.PI) angleDiff -= Math.PI * 2;
            while (angleDiff < -Math.PI) angleDiff += Math.PI * 2;
            plane.rotation += angleDiff * 0.08; // Turn away quickly
          } else {
            // Random wandering when far enough
            if (Math.random() < 0.03) {
              const angleChange = (Math.random() - 0.5) * 0.4;
              plane.rotation += angleChange;
            }
          }

          // Speed up when dispersing, slow down when wandering
          const targetSpeed = distFromCenter < 300 ? 2.0 : (0.8 + Math.random() * 0.4);
          const newSpeed = currentSpeed + (targetSpeed - currentSpeed) * 0.05;
          plane.vx = Math.cos(plane.rotation) * newSpeed;
          plane.vy = Math.sin(plane.rotation) * newSpeed;
        }

        // Update position
        plane.x += plane.vx;
        plane.y += plane.vy;

        // Wrap around screen
        if (plane.x < -50) plane.x = canvas.width + 50;
        if (plane.x > canvas.width + 50) plane.x = -50;
        if (plane.y < -50) plane.y = canvas.height + 50;
        if (plane.y > canvas.height + 50) plane.y = -50;

        // Draw
        drawTrail(plane.trail);
        drawPlane(plane);
      });

      animationId = requestAnimationFrame(update);
    }

    function onVisibilityChange() {
      if (document.hidden) mouseActive = false;
    }

    resize();
    window.addEventListener('resize', resize);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseleave', onMouseLeave);
    document.addEventListener('visibilitychange', onVisibilityChange);

    for (let i = 0; i < numPlanes; i++) {
      planes.push(createPlane());
    }

    update();

    return () => {
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseleave', onMouseLeave);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      clearTimeout(mouseTimeout);
      cancelAnimationFrame(animationId);
    };
  }

  onMount(() => {
    return initPlanesAnimation();
  });

  async function handleLogin(e: Event) {
    e.preventDefault();
    if (!email.trim() || !password) return;

    loading = true;
    error = null;

    try {
      await auth.login(email.trim(), password);
      goto('/');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Login failed';
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Login — Concord</title>
</svelte:head>

<div class="login-container">
  <!-- Breathing gradient background -->
  <div class="gradient-layer gradient-1"></div>
  <div class="gradient-layer gradient-2"></div>
  <div class="gradient-layer gradient-3"></div>
  <div class="gradient-layer gradient-4"></div>

  <!-- Flying planes canvas -->
  <canvas bind:this={canvas} class="planes-canvas"></canvas>

  <!-- Content -->
  <div class="relative z-10 w-full max-w-md px-4">
    <div class="mb-10 text-center">
      <div class="flex justify-center mb-5">
        <div class="logo-wrapper">
          <ConcordLogo size={112} class="text-accent" />
        </div>
      </div>
      <h1 class="text-5xl brand-text text-text-primary mb-2">Concord</h1>
      <div class="flex items-center justify-center gap-2 text-sm text-text-secondary mb-5">
        <span>by</span>
        <img
          src="/assets/corekinect-logo-dark.png"
          alt="CoreKinect"
          class="h-5 dark:hidden"
        />
        <img
          src="/assets/corekinect-logo.png"
          alt="CoreKinect"
          class="hidden h-5 dark:block"
        />
      </div>
      <p class="text-base text-text-secondary">
        Sign in to continue
      </p>
    </div>

    <div class="card card-lg shadow-xl backdrop-blur-md bg-surface-1/80 border border-white/10">
      {#if error}
        <div class="mb-4 rounded-lg bg-error-muted px-3 py-2 text-sm text-error">
          {error}
        </div>
      {/if}

      {#if loading}
        <div class="flex items-center justify-center py-4">
          <div class="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent"></div>
          <span class="ml-2 text-sm text-text-secondary">Signing in...</span>
        </div>
      {:else}
        <form onsubmit={handleLogin} class="space-y-4">
          <div>
            <label for="email" class="block text-sm font-medium text-text-secondary mb-1">Email</label>
            <input
              id="email"
              type="text"
              bind:value={email}
              placeholder="you@company.com"
              required
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder-text-tertiary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
          <div>
            <label for="password" class="block text-sm font-medium text-text-secondary mb-1">Password</label>
            <input
              id="password"
              type="password"
              bind:value={password}
              placeholder="Enter your password"
              required
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder-text-tertiary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
          <button
            type="submit"
            disabled={!email.trim() || !password}
            class="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Sign in
          </button>
        </form>
      {/if}

      <p class="mt-4 text-center text-xs text-text-tertiary">
        Only pre-registered accounts can login
      </p>
    </div>
  </div>
</div>

<style>
  .login-container {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-surface-0);
    position: relative;
    overflow: hidden;
  }

  /* Animated gradient layers */
  .gradient-layer {
    position: absolute;
    border-radius: 50%;
    filter: blur(100px);
    opacity: 0.35;
  }

  .gradient-1 {
    width: 600px;
    height: 600px;
    background: rgba(120, 80, 60, 0.4); /* Muted warm grey-brown */
    top: -200px;
    left: -150px;
    animation: drift1 15s ease-in-out infinite;
  }

  .gradient-2 {
    width: 500px;
    height: 500px;
    background: rgba(180, 100, 60, 0.3); /* Subtle orange-grey */
    bottom: -150px;
    right: -100px;
    animation: drift2 18s ease-in-out infinite;
  }

  .gradient-3 {
    width: 400px;
    height: 400px;
    background: rgba(100, 70, 120, 0.25); /* Muted purple-grey */
    top: 40%;
    left: 30%;
    animation: drift3 20s ease-in-out infinite;
  }

  .gradient-4 {
    width: 350px;
    height: 350px;
    background: rgba(160, 90, 50, 0.25); /* Warm grey */
    top: 20%;
    right: 20%;
    animation: drift4 12s ease-in-out infinite;
  }

  @keyframes drift1 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    33% { transform: translate(80px, 60px) scale(1.1); }
    66% { transform: translate(-40px, 100px) scale(0.9); }
  }

  @keyframes drift2 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    25% { transform: translate(-60px, -80px) scale(1.15); }
    50% { transform: translate(-100px, -40px) scale(0.95); }
    75% { transform: translate(-30px, -60px) scale(1.05); }
  }

  @keyframes drift3 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    20% { transform: translate(50px, -30px) scale(1.1); }
    40% { transform: translate(80px, 40px) scale(0.85); }
    60% { transform: translate(-20px, 60px) scale(1.05); }
    80% { transform: translate(-50px, 20px) scale(0.95); }
  }

  @keyframes drift4 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    30% { transform: translate(-70px, 50px) scale(1.2); }
    70% { transform: translate(40px, -30px) scale(0.9); }
  }

  :global(.dark) .gradient-1 { opacity: 0.4; }
  :global(.dark) .gradient-2 { opacity: 0.35; }
  :global(.dark) .gradient-3 { opacity: 0.3; }
  :global(.dark) .gradient-4 { opacity: 0.3; }

  .planes-canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    opacity: 0.8;
    z-index: 1;
  }

  :global(.dark) .planes-canvas {
    opacity: 0.6;
  }

  /* Logo animation */
  .logo-wrapper {
    animation: plane-float 3s ease-in-out infinite;
  }

  @keyframes plane-float {
    0%, 100% {
      transform: translateY(0) rotate(0deg);
    }
    50% {
      transform: translateY(-10px) rotate(2deg);
    }
  }
</style>
