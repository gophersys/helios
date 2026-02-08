<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { fade } from 'svelte/transition';
  import { loaderIn, loaderOut } from '$lib/utils/transitions';

  interface Props {
    /** Size of the animation area - 'sm' (200px), 'md' (300px), 'lg' (400px), 'full' (100%) */
    size?: 'sm' | 'md' | 'lg' | 'full';
    /** Number of planes */
    planeCount?: number;
    /** Show breathing gradient background */
    showGradient?: boolean;
    /** Optional message to display */
    message?: string;
  }

  let {
    size = 'md',
    planeCount = 5,
    showGradient = true,
    message = ''
  }: Props = $props();

  let canvas: HTMLCanvasElement;

  const sizeMap = {
    sm: { width: 200, height: 150 },
    md: { width: 300, height: 200 },
    lg: { width: 400, height: 300 },
    full: { width: 0, height: 0 }
  };

  interface Plane {
    x: number;
    y: number;
    vx: number;
    vy: number;
    size: number;
    rotation: number;
    trail: { x: number; y: number; alpha: number }[];
    // Orbit parameters for smooth centered motion
    orbitRadius: number;
    orbitSpeed: number;
    orbitAngle: number;
    orbitCenterX: number;
    orbitCenterY: number;
  }

  onMount(() => {
    if (!browser || !canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;
    const planes: Plane[] = [];

    function resize() {
      if (size === 'full') {
        canvas.width = canvas.parentElement?.clientWidth || 300;
        canvas.height = canvas.parentElement?.clientHeight || 200;
      } else {
        canvas.width = sizeMap[size].width;
        canvas.height = sizeMap[size].height;
      }
      // Update orbit centers when resized
      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;
      planes.forEach(plane => {
        plane.orbitCenterX = centerX + (Math.random() - 0.5) * 40;
        plane.orbitCenterY = centerY + (Math.random() - 0.5) * 30;
      });
    }

    function createPlane(): Plane {
      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;
      const orbitRadius = 30 + Math.random() * 50;
      const orbitAngle = Math.random() * Math.PI * 2;
      const orbitSpeed = 0.008 + Math.random() * 0.012; // Smooth orbit speed

      // Start at orbit position
      const x = centerX + Math.cos(orbitAngle) * orbitRadius;
      const y = centerY + Math.sin(orbitAngle) * orbitRadius;

      return {
        x,
        y,
        vx: 0,
        vy: 0,
        size: 6 + Math.random() * 4,
        rotation: orbitAngle + Math.PI / 2, // Face tangent to orbit
        trail: [],
        orbitRadius,
        orbitSpeed: orbitSpeed * (Math.random() > 0.5 ? 1 : -1), // Random direction
        orbitAngle,
        orbitCenterX: centerX + (Math.random() - 0.5) * 40,
        orbitCenterY: centerY + (Math.random() - 0.5) * 30
      };
    }

    function drawPlane(plane: Plane) {
      ctx!.save();
      ctx!.translate(plane.x, plane.y);
      ctx!.rotate(plane.rotation + Math.PI);

      const s = plane.size / 16;
      ctx!.strokeStyle = 'rgba(234, 88, 12, 0.8)';
      ctx!.lineWidth = 1.5 * s;
      ctx!.lineCap = 'round';
      ctx!.lineJoin = 'round';

      // Fuselage
      ctx!.beginPath();
      ctx!.moveTo((3 - 16) * s, 0);
      ctx!.lineTo((7 - 16) * s, -3 * s);
      ctx!.lineTo((12 - 16) * s, -4 * s);
      ctx!.lineTo((26 - 16) * s, -1.5 * s);
      ctx!.lineTo((30 - 16) * s, 0);
      ctx!.lineTo((26 - 16) * s, 1.5 * s);
      ctx!.lineTo((12 - 16) * s, 4 * s);
      ctx!.lineTo((7 - 16) * s, 3 * s);
      ctx!.closePath();
      ctx!.stroke();

      // Top wing
      ctx!.beginPath();
      ctx!.moveTo((14 - 16) * s, -4 * s);
      ctx!.lineTo((22 - 16) * s, -10 * s);
      ctx!.lineTo((24 - 16) * s, -2 * s);
      ctx!.stroke();

      // Bottom wing
      ctx!.beginPath();
      ctx!.moveTo((14 - 16) * s, 4 * s);
      ctx!.lineTo((22 - 16) * s, 10 * s);
      ctx!.lineTo((24 - 16) * s, 2 * s);
      ctx!.stroke();

      // Tail
      ctx!.beginPath();
      ctx!.moveTo((7 - 16) * s, -3 * s);
      ctx!.lineTo((11 - 16) * s, -8 * s);
      ctx!.stroke();

      ctx!.restore();
    }

    function drawTrail(trail: { x: number; y: number; alpha: number }[]) {
      trail.forEach((dot, i) => {
        const alpha = dot.alpha * 0.5;
        ctx!.beginPath();
        ctx!.arc(dot.x, dot.y, 1 + (i / trail.length) * 1.5, 0, Math.PI * 2);
        ctx!.fillStyle = `rgba(234, 88, 12, ${alpha})`;
        ctx!.fill();
      });
    }

    function update() {
      ctx!.clearRect(0, 0, canvas.width, canvas.height);

      planes.forEach(plane => {
        // Update orbit angle
        plane.orbitAngle += plane.orbitSpeed;

        // Add gentle drift to orbit center for organic feel
        plane.orbitCenterX += Math.sin(Date.now() * 0.001 + plane.orbitRadius) * 0.05;
        plane.orbitCenterY += Math.cos(Date.now() * 0.001 + plane.orbitRadius) * 0.03;

        // Keep orbit center near canvas center
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        plane.orbitCenterX += (centerX - plane.orbitCenterX) * 0.01;
        plane.orbitCenterY += (centerY - plane.orbitCenterY) * 0.01;

        // Calculate new position on orbit
        const newX = plane.orbitCenterX + Math.cos(plane.orbitAngle) * plane.orbitRadius;
        const newY = plane.orbitCenterY + Math.sin(plane.orbitAngle) * plane.orbitRadius;

        // Smoothly move toward orbit position
        plane.x += (newX - plane.x) * 0.1;
        plane.y += (newY - plane.y) * 0.1;

        // Update rotation to face direction of movement (tangent to orbit)
        const targetRotation = plane.orbitAngle + (plane.orbitSpeed > 0 ? Math.PI / 2 : -Math.PI / 2);
        // Smooth rotation
        let rotDiff = targetRotation - plane.rotation;
        while (rotDiff > Math.PI) rotDiff -= Math.PI * 2;
        while (rotDiff < -Math.PI) rotDiff += Math.PI * 2;
        plane.rotation += rotDiff * 0.08;

        // Trail
        const trailOffset = 8;
        const trailX = plane.x - Math.cos(plane.rotation) * trailOffset;
        const trailY = plane.y - Math.sin(plane.rotation) * trailOffset;
        plane.trail.push({ x: trailX, y: trailY, alpha: 0.35 });

        if (plane.trail.length > 20) {
          plane.trail.shift();
        }

        plane.trail.forEach(dot => {
          dot.alpha *= 0.92;
        });

        drawTrail(plane.trail);
        drawPlane(plane);
      });

      animationId = requestAnimationFrame(update);
    }

    resize();
    window.addEventListener('resize', resize);

    for (let i = 0; i < planeCount; i++) {
      planes.push(createPlane());
    }

    update();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animationId);
    };
  });
</script>

<div
  class="planes-loader"
  class:size-sm={size === 'sm'}
  class:size-md={size === 'md'}
  class:size-lg={size === 'lg'}
  class:size-full={size === 'full'}
  in:fade={loaderIn}
  out:fade={loaderOut}
>
  {#if showGradient}
    <div class="gradient-bg"></div>
  {/if}
  <canvas bind:this={canvas} class="planes-canvas"></canvas>
  {#if message}
    <p class="loader-message">{message}</p>
  {/if}
</div>

<style>
  .planes-loader {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }

  .size-sm {
    width: 200px;
    height: 150px;
  }

  .size-md {
    width: 300px;
    height: 200px;
  }

  .size-lg {
    width: 400px;
    height: 300px;
  }

  .size-full {
    width: 100%;
    height: 100%;
    min-height: 200px;
  }

  .gradient-bg {
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse at center, rgba(234, 88, 12, 0.08) 0%, transparent 65%);
    animation: pulse 4s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.6; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.03); }
  }

  .planes-canvas {
    position: relative;
    z-index: 1;
  }

  .loader-message {
    position: relative;
    z-index: 2;
    margin-top: 0.75rem;
    font-size: 0.8125rem;
    color: var(--color-text-tertiary);
    text-align: center;
    animation: fadeInUp 0.3s ease-out;
  }

  @keyframes fadeInUp {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
</style>
